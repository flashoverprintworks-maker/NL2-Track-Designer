"""
Simple speed and G-force estimation along a built track, using energy
conservation (+ an optional simplified friction/drag term) for speed,
and curvature + tangential acceleration for G-forces.

This is NOT a full rigid-body train dynamics simulation - real coaster
design software accounts for things like car mass distribution,
individual wheel friction, air resistance as a function of speed
squared, and multi-car train effects. This gives a reasonable, useful
estimate for comfort/intensity checking during design - "is this loop
too weak or too brutal" - not an engineering-certified simulation.

G-force convention (matches how NoLimits and most coaster physics
tools report it): +1G = normal seated force at rest on a level track.
Positive vertical G = pressed down into your seat harder than normal
(valleys, loop bottoms). Negative vertical G = airtime/ejector air
(cresting hills too fast, top of a loop taken too fast). Lateral G is a
sideways push; the sign just indicates direction (left vs right), not
"good" vs "bad".

Comfort/safety reference (ASTM F2291, the US amusement ride design
standard): brief-peak limits are roughly +5 to +6G vertical, -2G
vertical, and +-1.5G lateral, with the allowed value dropping sharply
the longer a force is sustained. This module only checks against those
brief-peak numbers - it doesn't model duration - so treat warnings as
"worth a second look", not a certification.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from .geometry import TrackPoint, v_sub, v_scale, v_dot

GRAVITY = 9.80665  # standard gravity, m/s^2
MIN_SPEED = 0.5  # m/s floor - avoids sqrt of a negative number outright

# ASTM F2291-referenced brief-peak comfort limits (see module docstring).
LIMIT_VERTICAL_G_MAX = 5.5
LIMIT_VERTICAL_G_MIN = -2.0
LIMIT_LATERAL_G = 1.5


def compute_speed_profile(points: List[TrackPoint], start_speed_ms: float,
                           friction_coef: float = 0.02) -> List[float]:
    """Speed (m/s) at each point, via energy conservation from
    start_speed_ms at points[0], losing `friction_coef * GRAVITY` worth
    of "effective height" per meter traveled - a simplified stand-in for
    combined rolling resistance and air drag (real losses depend on
    train mass, wheel type, and speed-squared drag, none of which this
    models). Clamped to MIN_SPEED rather than going to zero or
    imaginary; see `speed_warnings()` for where that clamping kicked in.
    """
    if not points:
        return []
    h0 = points[0].pos[1]
    speeds = []
    for p in points:
        dh = h0 - p.pos[1]
        friction_loss = friction_coef * GRAVITY * p.distance
        v_sq = start_speed_ms ** 2 + 2 * GRAVITY * dh - 2 * friction_loss
        speeds.append(math.sqrt(v_sq) if v_sq > MIN_SPEED ** 2 else MIN_SPEED)
    return speeds


def speed_warnings(points: List[TrackPoint], start_speed_ms: float,
                    friction_coef: float = 0.02) -> List[str]:
    """Distances (as human-readable messages) where the UNCLAMPED energy
    equation would have dropped below the speed floor - i.e. where this
    simplified free-rolling model says the train doesn't have enough
    momentum to be there. A real powered lift or launch section is the
    normal, expected reason this fires; it's not necessarily a mistake."""
    if not points:
        return []
    h0 = points[0].pos[1]
    out = []
    was_below = False
    for p in points:
        dh = h0 - p.pos[1]
        friction_loss = friction_coef * GRAVITY * p.distance
        v_sq = start_speed_ms ** 2 + 2 * GRAVITY * dh - 2 * friction_loss
        below = v_sq < MIN_SPEED ** 2
        if below and not was_below:
            out.append(f"Insufficient free-rolling energy from ~{p.distance:.0f}m "
                        f"(needs a powered lift/launch there, or less height/friction).")
        was_below = below
    return out


def compute_g_forces(points: List[TrackPoint], speeds: List[float]) -> List[Tuple[float, float]]:
    """Returns a list of (vertical_g, lateral_g) per point, using the
    track's curvature (rate of change of the front vector per unit arc
    length) for centripetal acceleration, plus the tangential
    acceleration from speed changes, combined with gravity. See the
    module docstring for the sign convention."""
    n = len(points)
    if n < 3:
        return [(1.0, 0.0)] * n

    out = []
    for i in range(n):
        i0 = max(0, i - 1)
        i1 = min(n - 1, i + 1)
        ds = points[i1].distance - points[i0].distance
        if ds < 1e-9:
            out.append((1.0, 0.0))
            continue

        d_front = v_sub(points[i1].front, points[i0].front)
        kappa = v_scale(d_front, 1.0 / ds)

        v = speeds[i]
        a_centripetal = v_scale(kappa, v * v)

        dv_ds = (speeds[i1] - speeds[i0]) / ds
        a_tangential = v_scale(points[i].front, v * dv_ds)

        a_car = [a_centripetal[j] + a_tangential[j] for j in range(3)]
        g_force_vec = [(a_car[j] - (0.0 if j != 1 else -GRAVITY)) / GRAVITY for j in range(3)]

        vertical_g = v_dot(g_force_vec, points[i].up)
        lateral_g = v_dot(g_force_vec, points[i].left)
        out.append((vertical_g, lateral_g))
    return out


def g_force_warnings(points: List[TrackPoint], g_forces: List[Tuple[float, float]]) -> List[str]:
    """Flags points exceeding the ASTM-referenced brief-peak limits.
    Collapses consecutive flagged points into one message per contiguous
    stretch rather than one per sample point."""
    out = []
    kind = None  # what the current contiguous stretch is flagged for
    start_dist = None
    peak = None

    def flush(end_dist):
        if kind is not None:
            out.append(f"{kind} between {start_dist:.0f}m and {end_dist:.0f}m (peak {peak:+.1f}G).")

    for p, (vg, lg) in zip(points, g_forces):
        this_kind = None
        this_peak = 0.0
        if vg > LIMIT_VERTICAL_G_MAX:
            this_kind, this_peak = "High positive vertical G", vg
        elif vg < LIMIT_VERTICAL_G_MIN:
            this_kind, this_peak = "Strong negative vertical G (airtime)", vg
        elif abs(lg) > LIMIT_LATERAL_G:
            this_kind, this_peak = "High lateral G", lg

        if this_kind != kind:
            flush(p.distance)
            kind, start_dist, peak = this_kind, p.distance, this_peak
        elif this_kind is not None and abs(this_peak) > abs(peak):
            peak = this_peak

    flush(points[-1].distance if points else 0.0)
    return out
