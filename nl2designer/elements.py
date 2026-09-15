"""
Element library.

Each function here returns an ElementSpec (see geometry.py) - a small,
declarative description of "how much pitch/yaw/roll happens over what
length". This is the layer meant to replace FVD++'s formula editor for
the general user: instead of writing force-vector formulas by hand, you
pick a named element and give it a few obvious parameters (radius,
angle, bank angle...).

Power users still get the full flexibility of FVD++ through `custom()`,
which exposes the raw pitch/yaw/roll/length contract directly - that's
the "versatility without the learning curve" trade: simple stuff is a
one-line call with named parameters, complex stuff drops down to the
same primitives FVD++ uses (rate of pitch/yaw/roll change over length),
without needing force-vector calculus to get there.
"""

from __future__ import annotations

import math

from .geometry import ElementSpec, ease_flat, ease_in_hold_out


def straight(length: float, name: str = "Straight") -> ElementSpec:
    """A straight, flat, unbanked section."""
    return ElementSpec(name=name, length=length)


def flat_turn(radius: float, angle_deg: float, direction: str = "left", name: str = None) -> ElementSpec:
    """A flat (unbanked) turn of `angle_deg` degrees at `radius` meters."""
    sign = 1.0 if direction == "left" else -1.0
    length = radius * math.radians(abs(angle_deg))
    return ElementSpec(
        name=name or f"Flat Turn {angle_deg:.0f} deg",
        length=length,
        total_yaw_deg=sign * angle_deg,
    )


def banked_turn(
    radius: float,
    angle_deg: float,
    bank_deg: float,
    direction: str = "left",
    transition_frac: float = 0.2,
    name: str = None,
) -> ElementSpec:
    """A turn that banks into the curve, holds the bank, then rolls back
    out. `transition_frac` is the fraction of the element's length spent
    rolling in (and the same fraction rolling out at the end)."""
    sign = 1.0 if direction == "left" else -1.0
    length = radius * math.radians(abs(angle_deg))
    roll_profile = ease_in_hold_out(transition_frac, transition_frac)
    return ElementSpec(
        name=name or f"Banked Turn {angle_deg:.0f} deg @ {bank_deg:.0f} deg bank",
        length=length,
        total_yaw_deg=sign * angle_deg,
        total_roll_deg=sign * bank_deg,
        roll_profile=roll_profile,
        # Yaw ramps with the bank too, so the turn doesn't "grip" hard
        # before the bank has built up.
        yaw_profile=roll_profile,
    )


def hill(radius: float, angle_deg: float, name: str = None) -> ElementSpec:
    """A vertical arc: positive angle_deg = crest (goes up then levels/over
    the top), negative = valley (dips down then levels). This is a single
    constant-radius arc; chain two of these (e.g. +20 then -20) to build a
    classic hill shape, or use `camelback()` for a ready-made hill."""
    length = radius * math.radians(abs(angle_deg))
    return ElementSpec(
        name=name or f"Hill Arc {angle_deg:.0f} deg",
        length=length,
        total_pitch_deg=angle_deg,
    )


def camelback(radius_top: float, crest_angle_deg: float, name: str = "Camelback Hill") -> ElementSpec:
    """Convenience wrapper: this is really just `hill()` with a friendlier
    name for the common case of a single airtime hill crest. For a full
    hill (up, over, down) chain hill(+angle) then hill(-angle)."""
    return hill(radius_top, crest_angle_deg, name=name)


def loop(radius: float, name: str = "Vertical Loop") -> ElementSpec:
    """A full 360 degree vertical loop. Circular for simplicity in this
    MVP (real loops are usually clothoid/teardrop-shaped for comfort -
    see `clothoid_loop()` for that version). Chain two of these (e.g.
    +20 then -20) to build a classic hill shape, or use `camelback()`
    for a ready-made hill."""
    length = radius * math.radians(360.0)
    return ElementSpec(
        name=name,
        length=length,
        total_pitch_deg=360.0,
        pitch_profile=ease_flat,
    )


def clothoid_loop(radius_bottom: float, radius_top: float, name: str = None) -> ElementSpec:
    """A vertical loop whose radius varies smoothly around the circuit -
    wide at the bottom, narrow at the top - the shape Werner Stengel
    introduced specifically to fix what a constant-radius loop can't:
    a circular loop needs a minimum entry speed to safely clear the top
    (v0^2 >= 5*g*R) that's mathematically ~5.4% higher than the fastest
    entry the ASTM F2291 comfort limit allows at the bottom (v0^2 <=
    4.5*g*R), for ANY single radius (see test_geometry.py for the
    proof). Widening the bottom radius keeps bottom G-force comfortable
    at higher speed, while narrowing the top radius means less speed is
    needed there to maintain contact - solving the problem a circle
    fundamentally can't.

    Implementation: the pitch rate is modulated by
    `1 - amplitude*cos(2*pi*u)` across the element's normalized
    progress u (0 = bottom/start, 0.5 = top, 1 = bottom/end), which
    integrates to the same total 360 degrees as a circular loop but
    concentrates more of the turning near the top (tighter radius
    there) and less near the bottom (wider radius there). `amplitude`
    is solved from the requested radii so the achieved bottom/top
    radii closely match what you asked for.
    """
    name = name or f"Clothoid Loop ({radius_bottom:.0f}m/{radius_top:.0f}m)"
    if radius_bottom <= 0 or radius_top <= 0:
        raise ValueError("clothoid_loop radii must be positive")
    amplitude = (radius_bottom - radius_top) / (radius_bottom + radius_top)
    amplitude = max(-0.9, min(0.9, amplitude))
    r_nominal = radius_bottom * (1 - amplitude)
    length = r_nominal * 2 * math.pi

    def profile(u: float) -> float:
        return 1 - amplitude * math.cos(2 * math.pi * u)

    return ElementSpec(
        name=name,
        length=length,
        total_pitch_deg=360.0,
        pitch_profile=profile,
    )


def helix(
    radius: float,
    num_turns: float,
    height_change: float,
    bank_deg: float,
    direction: str = "left",
    name: str = None,
) -> ElementSpec:
    """A banked helix that descends or climbs `height_change` meters
    (negative = descend) over `num_turns` full rotations."""
    sign = 1.0 if direction == "left" else -1.0
    yaw_total = 360.0 * num_turns
    flat_length = radius * math.radians(yaw_total)
    # Approximate the true (slightly longer, pitched) length via Pythagoras
    # against the requested height change - good enough for a helix pitch
    # shallow enough to ride comfortably.
    length = math.sqrt(flat_length**2 + height_change**2)
    pitch_deg = math.degrees(math.asin(max(-1.0, min(1.0, height_change / length))))
    return ElementSpec(
        name=name or f"Helix {num_turns:.1f} turns",
        length=length,
        total_yaw_deg=sign * yaw_total,
        total_pitch_deg=pitch_deg,
        total_roll_deg=sign * bank_deg,
        roll_profile=ease_in_hold_out(0.1, 0.1),
        yaw_profile=ease_in_hold_out(0.1, 0.1),
    )


def barrel_roll(length: float, num_rolls: float = 1.0, direction: str = "left", name: str = None) -> ElementSpec:
    """An inline roll (like a corkscrew but non-inverting overall track
    path - purely a roll about the direction of travel) over `length`
    meters, straight and flat otherwise."""
    sign = 1.0 if direction == "left" else -1.0
    return ElementSpec(
        name=name or f"Barrel Roll x{num_rolls:.1f}",
        length=length,
        total_roll_deg=sign * 360.0 * num_rolls,
    )


def zero_g_roll(radius: float, angle_deg: float, num_rolls: float, name: str = "Zero-G Roll") -> ElementSpec:
    """A hill arc combined with a roll - the classic "zero-g roll" element:
    pitches up and over like a hill while also rolling."""
    length = radius * math.radians(abs(angle_deg))
    return ElementSpec(
        name=name,
        length=length,
        total_pitch_deg=angle_deg,
        total_roll_deg=360.0 * num_rolls,
    )


def custom(
    length: float,
    total_pitch_deg: float = 0.0,
    total_yaw_deg: float = 0.0,
    total_roll_deg: float = 0.0,
    pitch_easing: str = "flat",
    yaw_easing: str = "flat",
    roll_easing: str = "flat",
    transition_frac: float = 0.2,
    name: str = "Custom Element",
) -> ElementSpec:
    """The power-user escape hatch: define any element directly in terms
    of the raw pitch/yaw/roll/length contract, same primitives FVD++
    exposes, just named instead of buried in a formula editor.

    easing choices: "flat" (constant rate) or "eased" (ramp in/hold/out,
    using `transition_frac` for the ramp portions).
    """

    def resolve(easing: str):
        if easing == "flat":
            return ease_flat
        if easing == "eased":
            return ease_in_hold_out(transition_frac, transition_frac)
        raise ValueError(f"Unknown easing '{easing}', use 'flat' or 'eased'")

    return ElementSpec(
        name=name,
        length=length,
        total_pitch_deg=total_pitch_deg,
        total_yaw_deg=total_yaw_deg,
        total_roll_deg=total_roll_deg,
        pitch_profile=resolve(pitch_easing),
        yaw_profile=resolve(yaw_easing),
        roll_profile=resolve(roll_easing),
    )


# ---------------------------------------------------------------------------
# Named elements drawn from real manufacturers (B&M, Intamin, Mack, RMC, and
# the Stengel/Arrow/Vekoma lineage behind several of these). Sourced against
# Coasterpedia, the Roller Coaster Wiki, and Wikipedia's list of roller
# coaster elements rather than guessed. A few (Cobra Roll especially) are
# genuinely complex 3D shapes that this engine's straight-line-of-primitives
# model can only approximate - see each docstring for what's exact vs
# approximated, and why.
#
# Several of these return a LIST of ElementSpec rather than one - Track.add()
# accepts either and flattens automatically, so from the palette/GUI's point
# of view a composite is still a single element you drag in and edit as a
# whole; it just expands into multiple track segments (with their own names,
# visible in the summary panel) when built.
# ---------------------------------------------------------------------------


def immelmann(radius: float, direction: str = "left", name: str = None) -> list:
    """B&M signature inversion, named after the WW1 aerial maneuver. Climbs
    through a half vertical loop (inverted at the top, already facing the
    reverse direction - a pure 180 degree pitch change flips heading as a
    geometric side effect, which is exactly what the real element does),
    then a half twist (roll) to exit upright, continuing in that reversed
    direction. An Immelmann flown/ridden in reverse is a Dive Loop."""
    base = name or "Immelmann"
    sign = 1.0 if direction == "left" else -1.0
    climb = hill(radius, 180.0, name=f"{base} (half loop)")
    twist_len = max(radius * 0.6, 3.0)
    twist = ElementSpec(name=f"{base} (half twist)", length=twist_len, total_roll_deg=sign * 180.0)
    return [climb, twist]


def dive_loop(radius: float, direction: str = "left", name: str = None) -> list:
    """B&M signature inversion - an Immelmann run in reverse order: twists
    upward/sideways first (half roll, still moving in the original
    direction), then dives down through a half vertical loop toward the
    ground, exiting upright and reversed."""
    base = name or "Dive Loop"
    sign = 1.0 if direction == "left" else -1.0
    twist_len = max(radius * 0.6, 3.0)
    twist = ElementSpec(name=f"{base} (half twist)", length=twist_len, total_roll_deg=sign * 180.0)
    dive = hill(radius, -180.0, name=f"{base} (half loop)")
    return [twist, dive]


def sidewinder(radius: float, direction: str = "left", name: str = None) -> list:
    """Half of a vertical loop combined with half of a corkscrew - visually
    close to an Immelmann, but exits at roughly a right angle to the
    entrance rather than a full reversal. Modeled here as an Immelmann-style
    half loop, then a half twist with an added quarter turn of yaw so the
    exit heading lands near 90 degrees instead of 180 - the sources
    describing this element note it's easily confused with an Immelmann and
    the two are often distinguished mainly by that exit angle."""
    base = name or "Sidewinder"
    sign = 1.0 if direction == "left" else -1.0
    climb = hill(radius, 180.0, name=f"{base} (half loop)")
    twist_len = max(radius * 0.6, 3.0)
    twist = ElementSpec(
        name=f"{base} (half twist)",
        length=twist_len,
        total_roll_deg=sign * 180.0,
        total_yaw_deg=sign * 90.0,
        yaw_profile=ease_in_hold_out(0.3, 0.3),
    )
    return [climb, twist]


def cobra_roll(radius: float, direction: str = "left", name: str = None) -> list:
    """B&M/Intamin double inversion resembling a striking cobra's head:
    two half vertical loops joined by two mirrored half-corkscrews, exiting
    upright and travelling the opposite direction from entry.

    APPROXIMATION NOTE: the real element's middle "half-corkscrew" sections
    curve noticeably sideways (that lateral offset is what keeps the two
    loop halves from structurally colliding, and is a big part of the
    shape's signature look). This engine models it as two combined
    loop+turn arcs instead of four separate loop/corkscrew/corkscrew/loop
    phases - it reproduces the right topology (two inversions, exits
    reversed and upright, verified by test) but not the exact real-world
    silhouette. Treat it as a solid placeholder, not a precise replica."""
    base = name or "Cobra Roll"
    sign = 1.0 if direction == "left" else -1.0
    arc_len = radius * math.radians(180.0)
    seg1 = ElementSpec(
        name=f"{base} (first inversion)", length=arc_len,
        total_pitch_deg=180.0, total_yaw_deg=sign * 90.0,
        yaw_profile=ease_in_hold_out(0.25, 0.25),
    )
    seg2 = ElementSpec(
        name=f"{base} (second inversion)", length=arc_len,
        total_pitch_deg=180.0, total_yaw_deg=sign * 90.0,
        yaw_profile=ease_in_hold_out(0.25, 0.25),
    )
    return [seg1, seg2]


def corkscrew(length: float, direction: str = "left", name: str = None) -> ElementSpec:
    """The classic Arrow Dynamics inversion (1975's Corkscrew at Knott's
    Berry Farm) - a single 360 degree roll while continuing forward.
    Mechanically identical to `barrel_roll()` with one rotation; also
    historically called a Heartline Roll. Given its own named entry since
    "Corkscrew" is the term most riders and enthusiasts actually use."""
    return barrel_roll(length, num_rolls=1.0, direction=direction, name=name or "Corkscrew")


def wave_turn(radius: float, angle_deg: float = 40.0, bank_deg: float = 90.0,
              direction: str = "left", name: str = None) -> ElementSpec:
    """Rocky Mountain Construction's signature element (they coined the
    term) - an airtime hill ridden while banked a full 90 degrees, rather
    than flat. Modeled as a hill arc with the roll target held at bank_deg
    throughout. Chain a second wave_turn with a negative angle to complete
    a full hill shape, same as with `hill()`."""
    sign = 1.0 if direction == "left" else -1.0
    length = radius * math.radians(abs(angle_deg))
    return ElementSpec(
        name=name or f"Wave Turn {angle_deg:.0f} deg",
        length=length,
        total_pitch_deg=angle_deg,
        total_roll_deg=sign * bank_deg,
        roll_profile=ease_in_hold_out(0.2, 0.2),
    )


def outward_banked_turn(radius: float, angle_deg: float, bank_deg: float = 45.0,
                         direction: str = "left", transition_frac: float = 0.2,
                         name: str = None) -> ElementSpec:
    """RMC's "outward banked" turn (also marketed as part of their Wave
    Turn family) - a turn banked the opposite way from a conventional
    banked turn: away from the curve instead of into it. This is what
    produces the distinctive sideways-airtime "thrown outward" sensation
    riders describe. Mechanically identical to `banked_turn()` except the
    roll direction is inverted relative to the turn direction."""
    sign = 1.0 if direction == "left" else -1.0
    length = radius * math.radians(abs(angle_deg))
    roll_profile = ease_in_hold_out(transition_frac, transition_frac)
    return ElementSpec(
        name=name or f"Outward Banked Turn {angle_deg:.0f} deg",
        length=length,
        total_yaw_deg=sign * angle_deg,
        total_roll_deg=-sign * bank_deg,  # opposite sign from banked_turn - the whole point
        roll_profile=roll_profile,
        yaw_profile=roll_profile,
    )


def stengel_dive(radius: float, hill_angle_deg: float = 35.0, turn_angle_deg: float = 60.0,
                  bank_deg: float = 110.0, direction: str = "left", name: str = None) -> list:
    """The only element named after its designer (Werner Stengel, whose
    consultancy has worked on roller coasters for nearly every major
    manufacturer) - a camelback hill that tilts beyond 90 degrees at the
    very crest, combining an airtime hill with an overbanked turn, then
    releases back to level on the way down. Used on Intamin and Mack
    hypercoasters (e.g. Goliath at Walibi Holland, Flash at Lewa
    Adventure)."""
    base = name or "Stengel Dive"
    sign = 1.0 if direction == "left" else -1.0
    climb = hill(radius, hill_angle_deg, name=f"{base} (climb)")
    crest_len = max(radius * 0.5, 8.0)
    ease = ease_in_hold_out(0.25, 0.25)
    crest = ElementSpec(
        name=f"{base} (overbanked crest)", length=crest_len,
        total_yaw_deg=sign * turn_angle_deg, total_roll_deg=sign * bank_deg,
        roll_profile=ease, yaw_profile=ease,
    )
    descend = ElementSpec(
        name=f"{base} (descend)", length=radius * math.radians(abs(hill_angle_deg)),
        total_pitch_deg=-hill_angle_deg, total_roll_deg=-sign * bank_deg,
        roll_profile=ease_in_hold_out(0.3, 0.3),
    )
    return [climb, crest, descend]


def lift_hill(
    height: float,
    angle_deg: float = 30.0,
    bottom_transition_radius: float = 12.0,
    top_transition_radius: float = 18.0,
    name: str = None,
) -> list:
    """A complete lift hill: a curve up from level to the lift angle, a
    straight run at that angle covering most of the climb, and a curve
    back to level at the crest - built to reach exactly `height` meters
    of total vertical rise, regardless of angle or transition radii.

    Real lift hill angles vary a lot by era and mechanism, which is the
    whole point of the manufacturer-style presets built on top of this
    (see registry.py): a traditional chain lift is commonly cited around
    30 degrees; Intamin's cable lift on Millennium Force was deliberately
    built steeper, at 45 degrees, specifically to shrink the footprint a
    30-degree chain lift would have needed; older/wooden-coaster chain
    lifts often ran shallower, 20-25 degrees; and some modern coasters
    (Gerstlauer, some Intamin models) use a near-vertical elevator-style
    lift. This function takes the angle as a plain parameter so any of
    those (or anything in between) is just a different preset.

    Height accounting: each circular transition arc contributes
    radius*(1-cos(angle)) meters of rise on its own; the remaining height
    is covered by the straight run at sin(angle) meters of rise per meter
    of track. Raises ValueError if the requested height is too small for
    the chosen transition radii (i.e. the transitions alone would already
    overshoot it) - use a smaller radius or greater height.
    """
    angle_rad = math.radians(angle_deg)
    transition_rise = (
        bottom_transition_radius * (1 - math.cos(angle_rad))
        + top_transition_radius * (1 - math.cos(angle_rad))
    )
    straight_rise_needed = height - transition_rise
    if straight_rise_needed <= 0:
        raise ValueError(
            f"Requested lift height ({height:.1f}m) is too small for these transition "
            f"radii at {angle_deg:.0f} degrees (they alone need {transition_rise:.1f}m of "
            f"height). Increase the height, or use smaller transition radii."
        )
    straight_length = straight_rise_needed / math.sin(angle_rad)

    base = name or "Lift Hill"
    bottom = hill(bottom_transition_radius, angle_deg, name=f"{base} (bottom transition)")
    run = straight(straight_length, name=f"{base} (chain run)")
    top = hill(top_transition_radius, -angle_deg, name=f"{base} (crest transition)")
    return [bottom, run, top]
