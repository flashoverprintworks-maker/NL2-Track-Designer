"""
Core math engine for the coaster track builder.

Coordinate system (matches NoLimits 2):
    X = right, Y = up, Z = ... (forward/back in the horizontal plane)
    Y is always "up" in the world.

A track is built by walking a "Frame" (an orthonormal basis) along the
path, one small step at a time. At every step we know:
    front  - unit vector pointing in the direction of travel
    left   - unit vector pointing to the rider's left
    up     - unit vector pointing towards the rider's head (banking)

Turning the front vector left/right is YAW.
Tipping the front vector up/down is PITCH.
Rotating around the front vector (banking) is ROLL.

Each Element (see elements.py) describes how much total pitch, yaw and
roll happen over its length, using an easing curve so the rates ramp
on and off smoothly (this is what keeps the ride "jerk" reasonable
instead of snapping to a G-force instantly, and is the same idea
FVD++ uses under the hood).

NL2's CSV spline importer only strictly needs Position + Up per point
(Front/Left can be written as zero and NL2 recomputes them), so that's
all export.py needs from here - but we track a full orthonormal frame
internally so the math stays numerically correct.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Sequence

Vec3 = List[float]  # simple [x, y, z]


def v_add(a: Vec3, b: Vec3) -> Vec3:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def v_sub(a: Vec3, b: Vec3) -> Vec3:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def v_scale(a: Vec3, s: float) -> Vec3:
    return [a[0] * s, a[1] * s, a[2] * s]


def v_dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a: Vec3, b: Vec3) -> Vec3:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def v_length(a: Vec3) -> float:
    return math.sqrt(v_dot(a, a))


def v_normalize(a: Vec3) -> Vec3:
    length = v_length(a)
    if length < 1e-12:
        raise ValueError("Cannot normalize a zero-length vector")
    return v_scale(a, 1.0 / length)


def rotate_about_axis(vec: Vec3, axis: Vec3, angle_rad: float) -> Vec3:
    """Rotate `vec` around a unit `axis` by `angle_rad` radians (Rodrigues' formula)."""
    axis = v_normalize(axis)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    term1 = v_scale(vec, cos_a)
    term2 = v_scale(v_cross(axis, vec), sin_a)
    term3 = v_scale(axis, v_dot(axis, vec) * (1 - cos_a))
    return v_add(v_add(term1, term2), term3)


@dataclass
class Frame:
    """An orthonormal basis + position at one point along the track."""

    pos: Vec3
    front: Vec3
    left: Vec3
    up: Vec3

    def copy(self) -> "Frame":
        return Frame(list(self.pos), list(self.front), list(self.left), list(self.up))

    def renormalize(self) -> None:
        """Re-orthonormalize the basis to stop floating point drift from
        accumulating over a long track (Gram-Schmidt)."""
        front = v_normalize(self.front)
        up = v_sub(self.up, v_scale(front, v_dot(self.up, front)))
        up = v_normalize(up)
        left = v_cross(up, front)  # right-handed: left = up x front
        left = v_normalize(left)
        self.front, self.left, self.up = front, left, up

    @staticmethod
    def start(
        pos: Sequence[float] = (0.0, 0.0, 0.0),
        heading_deg: float = 0.0,
    ) -> "Frame":
        """A new frame at `pos`, facing along +Z rotated by `heading_deg`
        around the world up axis (Y), with the car upright (up = +Y)."""
        front = [math.sin(math.radians(heading_deg)), 0.0, math.cos(math.radians(heading_deg))]
        up = [0.0, 1.0, 0.0]
        left = v_cross(up, front)
        return Frame(pos=list(pos), front=front, left=left, up=up)


@dataclass
class TrackPoint:
    """One sampled point of the finished track."""

    distance: float  # cumulative arc length from the start of the track, meters
    pos: Vec3
    front: Vec3
    left: Vec3
    up: Vec3


# A RateProfile is a function of normalized progress u in [0, 1] -> the
# instantaneous rate multiplier (0..~ a bit over 1) used to shape how
# quickly pitch/yaw/roll change turns on and off across an element.
RateProfile = Callable[[float], float]


def ease_flat(_u: float) -> float:
    """Constant rate the whole way (sharp on/off - use for simple elements)."""
    return 1.0


def ease_smoothstep(u: float) -> float:
    """Smooth ramp up, hold isn't implied here - see `ease_in_hold_out` for that.
    This alone ramps 0->1->0 like a single smooth bump, useful for elements
    that are *entirely* a transition (e.g. a roll-only barrel roll element)."""
    # A single smooth bump across the whole element: sin(pi*u) normalized so
    # the *average* rate integrates to the same total angle as a flat rate.
    return (math.pi / 2.0) * math.sin(math.pi * u)


def ease_in_hold_out(in_frac: float = 0.25, out_frac: float = 0.25) -> RateProfile:
    """Rate ramps up over the first `in_frac` of the element, holds steady,
    then ramps down over the last `out_frac`. This is the profile you want
    for banked turns (roll in, hold bank, roll out) so entry/exit isn't a
    sudden snap. Returned function is normalized so total integral == 1
    over u in [0,1], i.e. the element still ends at the exact target angle.
    """
    if in_frac + out_frac >= 1.0:
        raise ValueError("in_frac + out_frac must be < 1.0")
    hold_frac = 1.0 - in_frac - out_frac

    # Unnormalized shape: half-sine ramps up/down, flat top of height 1.
    def raw(u: float) -> float:
        if u < in_frac:
            return math.sin((u / in_frac) * (math.pi / 2.0))
        if u < in_frac + hold_frac:
            return 1.0
        u2 = (u - in_frac - hold_frac) / out_frac
        return math.sin((1.0 - u2) * (math.pi / 2.0))

    # Integrate the raw shape numerically once to find the normalizing constant.
    steps = 200
    total = sum(raw(i / steps) for i in range(steps)) / steps
    if total < 1e-9:
        total = 1.0

    def profile(u: float) -> float:
        return raw(u) / total

    return profile


@dataclass
class ElementSpec:
    """Describes one track element in terms of total angle changes over a
    given length, each with its own easing profile. This is the contract
    every function in elements.py produces."""

    name: str
    length: float  # meters of track (arc length along the front vector)
    total_pitch_deg: float = 0.0  # + = nose up, integrated about Left axis
    total_yaw_deg: float = 0.0  # + = turn left, integrated about Up axis
    total_roll_deg: float = 0.0  # + = bank left (roll about Front axis)
    pitch_profile: RateProfile = ease_flat
    yaw_profile: RateProfile = ease_flat
    roll_profile: RateProfile = ease_flat
    # Optional metadata carried through to the exported element for humans.
    meta: dict = field(default_factory=dict)


def integrate_element(
    start_frame: Frame, spec: ElementSpec, start_distance: float, step_size: float = 0.25
) -> List[TrackPoint]:
    """Walk `start_frame` along `spec`, returning sampled TrackPoints.
    `step_size` is the target distance in meters between samples (finer =
    smoother export, coarser = smaller file). The first returned point is
    the *start* of the element (so consecutive elements share a point;
    callers should drop the duplicate when concatenating elements)."""

    if spec.length <= 0:
        raise ValueError(f"Element '{spec.name}' has non-positive length")

    n_steps = max(1, math.ceil(spec.length / step_size))
    ds = spec.length / n_steps

    frame = start_frame.copy()
    points: List[TrackPoint] = [
        TrackPoint(start_distance, list(frame.pos), list(frame.front), list(frame.left), list(frame.up))
    ]

    pitch_total_rad = math.radians(spec.total_pitch_deg)
    yaw_total_rad = math.radians(spec.total_yaw_deg)
    roll_total_rad = math.radians(spec.total_roll_deg)

    dist = start_distance
    world_up = [0.0, 1.0, 0.0]
    for i in range(n_steps):
        u_mid = (i + 0.5) / n_steps  # sample rate at the midpoint of this step

        d_pitch = pitch_total_rad * spec.pitch_profile(u_mid) * (ds / spec.length)
        d_yaw = yaw_total_rad * spec.yaw_profile(u_mid) * (ds / spec.length)
        d_roll = roll_total_rad * spec.roll_profile(u_mid) * (ds / spec.length)

        # Move forward first (position uses the frame's current orientation).
        frame.pos = v_add(frame.pos, v_scale(frame.front, ds))

        # Pitch: rotate front/up about the car's CURRENT left axis (local).
        # This is what lets a vertical loop sweep front through a full
        # circle without any singularity, regardless of current heading
        # or bank. Negated here so the ElementSpec convention holds:
        # positive total_pitch_deg = nose up (climbing), matching every
        # caller's documented expectation (hill(), lift_hill(), etc.) -
        # without the negation, a positive rotation about +left actually
        # pitches the nose down given this frame's handedness.
        pivot_left = frame.left
        frame.front = rotate_about_axis(frame.front, pivot_left, -d_pitch)
        frame.up = rotate_about_axis(frame.up, pivot_left, -d_pitch)

        # Yaw: a RIGID rotation of the whole frame (front, left, up)
        # about the fixed WORLD vertical axis, not the car's own (possibly
        # banked) up axis. Rotating any vector about the world-vertical
        # axis leaves its vertical component unchanged - so a turn with
        # no requested pitch change now provably stays level, and an
        # existing bank angle is carried around the curve unchanged
        # instead of drifting. This is the fix for the height-drift issue.
        frame.front = rotate_about_axis(frame.front, world_up, d_yaw)
        frame.left = rotate_about_axis(frame.left, world_up, d_yaw)
        frame.up = rotate_about_axis(frame.up, world_up, d_yaw)

        # Roll: rotate up/left about the car's current front axis (local -
        # banking is always "around the direction of travel" by definition).
        frame.up = rotate_about_axis(frame.up, frame.front, d_roll)
        frame.left = rotate_about_axis(frame.left, frame.front, d_roll)

        frame.renormalize()

        dist += ds
        points.append(TrackPoint(dist, list(frame.pos), list(frame.front), list(frame.left), list(frame.up)))

    return points


def offset_points(points: List[TrackPoint], offset: float) -> List[TrackPoint]:
    """Shift a path `offset` meters along each point's *local* down
    direction (-up), turning a heartline path into a physical rail
    centerline (or vice versa with a negative offset).

    This is the standard "offset along the moving frame" approximation
    used to go from a heartline to rails: it keeps the same distance/
    frame at each sample and just displaces position. For very tight
    radii the true offset curve's arc length differs slightly from the
    source curve's (a small, known simplification - fine at the offsets
    and radii typical of full-size coasters).
    """
    out = []
    for p in points:
        new_pos = v_sub(p.pos, v_scale(p.up, offset))
        out.append(TrackPoint(p.distance, new_pos, list(p.front), list(p.left), list(p.up)))
    return out


def apply_roughness(points: List[TrackPoint], amplitude_deg: float, seed: float = 0.0) -> List[TrackPoint]:
    """Perturb a finished path with a small, deterministic "wobble" in
    banking - meant to stand in for the un-eased, hand-surveyed feel of
    track designed without modern CAD (Arrow Dynamics being the classic
    example). Rotates the up/left vectors slightly around the front axis
    at each point, by an amount that drifts smoothly (a sum of a few
    non-integer-ratio sine waves over cumulative distance, so it doesn't
    read as a perfectly periodic, obviously-fake ripple) rather than by
    literal per-point random noise, which would make the rails visibly
    jagged instead of just imprecise. `amplitude_deg` is the peak wobble;
    0 disables this entirely (the default everywhere it's used).

    This only touches orientation, not position - it will not fight the
    heartline offset math (apply it to the already-offset rail points,
    not the design heartline) and can't introduce self-intersecting
    geometry the way a positional jitter could.
    """
    if amplitude_deg <= 0:
        return points

    out = []
    for p in points:
        d = p.distance + seed
        wobble_deg = amplitude_deg * (
            0.55 * math.sin(d * 0.31) + 0.30 * math.sin(d * 0.83 + 1.7) + 0.15 * math.sin(d * 1.97 + 0.4)
        )
        up = rotate_about_axis(p.up, p.front, math.radians(wobble_deg))
        left = rotate_about_axis(p.left, p.front, math.radians(wobble_deg))
        out.append(TrackPoint(p.distance, list(p.pos), list(p.front), left, up))
    return out
