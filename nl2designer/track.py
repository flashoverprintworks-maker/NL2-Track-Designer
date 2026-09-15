"""
Track: a sequence of elements chained end-to-end. This is the "drag and
drop list" data model - in the eventual GUI, dragging elements onto the
canvas just appends/inserts ElementSpecs into a Track's element list.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import List

from .geometry import (
    ElementSpec, Frame, TrackPoint, integrate_element, offset_points,
    apply_roughness, ease_flat,
)
from .physics import compute_speed_profile, compute_g_forces, speed_warnings, g_force_warnings


@dataclass
class Track:
    name: str = "Untitled Track"
    start_pos: tuple = (0.0, 0.0, 0.0)
    start_heading_deg: float = 0.0
    elements: List[ElementSpec] = field(default_factory=list)
    step_size: float = 0.25  # meters between exported sample points
    heartline_offset: float = 1.1  # meters: distance from the design path
    # (heartline, where a rider's center of mass travels - what all the
    # roll/pitch/yaw math is defined relative to) down to the physical
    # rail centerline. ~1.0-1.2m is typical for a sit-down coaster;
    # adjust for other car types, or set to 0 to export the heartline
    # itself with no offset.

    arrow_style: bool = False
    # When true, every element's pitch/yaw/roll transitions become
    # constant-rate (ease_flat) instead of whatever smooth profile the
    # element normally uses - the G-force arrives all at once at each
    # element boundary instead of ramping in, instead of the smooth
    # clothoid-style ramps modern (post-CAD) manufacturers use. This is
    # the single biggest reason hand-drafted, pre-CAD track (Arrow
    # Dynamics being the textbook example) feels abrupt compared to
    # modern coasters - see README for more.
    roughness_deg: float = 0.0
    # Peak degrees of banking "wobble" layered onto the finished rail
    # path - stands in for the imprecise, hand-surveyed feel of track
    # built without modern measurement/CAD tools. 0 = off. A little goes
    # a long way; try 0.3-0.8 before going further.

    start_speed_ms: float = 2.0  # m/s at the very first point of the
    # track (e.g. leaving the station). Energy conservation carries this
    # forward for the speed/G-force estimate - see physics.py. If your
    # layout includes a chain lift, treat the pre-lift-crest numbers as
    # not physically meaningful (a real lift is chain-driven, not
    # momentum-driven); the simulation becomes meaningful again from the
    # top of the lift onward.
    friction_coef: float = 0.02  # simplified rolling+air resistance;
    # see physics.py docstring for what this does and doesn't model.

    def add(self, spec) -> "Track":
        """Append an element. Accepts a single ElementSpec, or a list of
        them (composite elements like Immelmann/Cobra Roll return a list -
        this flattens it so the rest of the pipeline doesn't need to care).
        Returns self so calls can be chained."""
        if isinstance(spec, list):
            self.elements.extend(spec)
        else:
            self.elements.append(spec)
        return self

    def _effective_elements(self) -> List[ElementSpec]:
        """The element list actually used to build the track - with
        transitions flattened to constant-rate if arrow_style is on.
        Never mutates the stored elements (so toggling the style back off
        restores the original smooth profiles)."""
        if not self.arrow_style:
            return self.elements
        return [
            replace(e, pitch_profile=ease_flat, yaw_profile=ease_flat, roll_profile=ease_flat)
            for e in self.elements
        ]

    def build(self) -> List[TrackPoint]:
        """Integrate every element in order and return the full list of
        sampled TrackPoints along the HEARTLINE (the design path all the
        roll/pitch/yaw math is defined relative to)."""
        if not self.elements:
            raise ValueError("Track has no elements to build")

        frame = Frame.start(pos=self.start_pos, heading_deg=self.start_heading_deg)
        all_points: List[TrackPoint] = []
        distance = 0.0

        for i, spec in enumerate(self._effective_elements()):
            pts = integrate_element(frame, spec, start_distance=distance, step_size=self.step_size)
            if i == 0:
                all_points.extend(pts)
            else:
                # Skip the first point of each subsequent element - it's a
                # duplicate of the previous element's last point.
                all_points.extend(pts[1:])

            # Carry the ending frame/distance forward into the next element.
            last = pts[-1]
            frame = Frame(pos=last.pos, front=last.front, left=last.left, up=last.up)
            distance = last.distance

        return all_points

    def build_rail_points(self) -> List[TrackPoint]:
        """The heartline path, offset down to the physical rail centerline
        by `heartline_offset`, with roughness (if any) applied last. This
        is what should actually be exported to NL2 (the CSV importer
        wants the rail path, not the heartline)."""
        heartline_pts = self.build()
        rail_pts = heartline_pts if abs(self.heartline_offset) < 1e-9 else offset_points(heartline_pts, self.heartline_offset)
        if self.roughness_deg > 0:
            rail_pts = apply_roughness(rail_pts, self.roughness_deg)
        return rail_pts

    def total_length(self) -> float:
        return sum(e.length for e in self.elements)

    def closure_offset(self, points: List[TrackPoint] = None) -> dict:
        """How far the LAST point of `points` (default: build_rail_points())
        is from the track's start position, broken out by axis - meant to
        help close a loop back to the station, the same way you'd check
        this by hand while iterating on closing turns. Returns a dict:
        {"dx", "dy", "dz", "distance"} - dx/dy/dz are signed (end minus
        start) in the same X/Y/Z sense NL2 and the rest of this program
        use; "distance" is the straight-line 3D distance."""
        if points is None:
            points = self.build_rail_points()
        if not points:
            return {"dx": 0.0, "dy": 0.0, "dz": 0.0, "distance": 0.0}
        start = points[0].pos
        end = points[-1].pos
        dx, dy, dz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
        return {"dx": dx, "dy": dy, "dz": dz, "distance": math.sqrt(dx * dx + dy * dy + dz * dz)}

    def row_end_distances(self, row_element_counts: List[int]) -> List[float]:
        """Given how many flattened ElementSpecs each "row" (palette item)
        contributed - composites like Immelmann/Cobra Roll/Lift Hill expand
        to more than one - returns the cumulative arc-length distance at
        the end of each row, for looking up "where was I after row N" in
        a built points list (e.g. to show closure at a selected element,
        not just at the end of the whole track)."""
        out = []
        idx = 0
        running = 0.0
        for count in row_element_counts:
            for _ in range(count):
                if idx < len(self.elements):
                    running += self.elements[idx].length
                    idx += 1
            out.append(running)
        return out

    def speed_profile(self, points: List[TrackPoint] = None) -> List[float]:
        """Estimated speed (m/s) at each point - see physics.py."""
        if points is None:
            points = self.build_rail_points()
        return compute_speed_profile(points, self.start_speed_ms, self.friction_coef)

    def g_forces(self, points: List[TrackPoint] = None, speeds: List[float] = None):
        """Estimated (vertical_g, lateral_g) at each point - see physics.py."""
        if points is None:
            points = self.build_rail_points()
        if speeds is None:
            speeds = self.speed_profile(points)
        return compute_g_forces(points, speeds)

    def physics_warnings(self, points: List[TrackPoint] = None) -> List[str]:
        """Human-readable warnings for both insufficient free-rolling
        energy (see speed_warnings) and G-forces exceeding the
        ASTM-referenced brief-peak comfort limits (see g_force_warnings)."""
        if points is None:
            points = self.build_rail_points()
        speeds = self.speed_profile(points)
        gforces = self.g_forces(points, speeds)
        return speed_warnings(points, self.start_speed_ms, self.friction_coef) + g_force_warnings(points, gforces)

    def summary(self) -> str:
        lines = [f"Track: {self.name}  ({self.total_length():.1f} m total)"]
        running = 0.0
        for e in self.elements:
            running += e.length
            lines.append(
                f"  - {e.name:<32} len={e.length:6.1f}m  "
                f"pitch={e.total_pitch_deg:+6.1f}  yaw={e.total_yaw_deg:+6.1f}  "
                f"roll={e.total_roll_deg:+6.1f}   (end @ {running:.1f}m)"
            )
        return "\n".join(lines)
