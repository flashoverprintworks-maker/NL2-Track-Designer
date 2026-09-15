"""
Export to NoLimits 2's documented CSV spline format
(Coaster tab -> Import -> Track Spline in NL2).

Per NL2's official file format reference, each row is:
    No., PosX, PosY, PosZ, FrontX, FrontY, FrontZ, LeftX, LeftY, LeftZ, UpX, UpY, UpZ
tab-separated (despite the .csv extension), one row per point, ordinal
starting at 1. Front/Left may be written as 0 - NL2 derives Front from
the spline positions and Left from Front x Up, so only Position and Up
are strictly required. We still write the real Front we computed
(harmless, and useful if you open the file yourself to sanity-check it).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from .geometry import TrackPoint, v_dot, v_length


HEADER = [
    "No.", "PosX", "PosY", "PosZ",
    "FrontX", "FrontY", "FrontZ",
    "LeftX", "LeftY", "LeftZ",
    "UpX", "UpY", "UpZ",
]


def validate_points(points: List[TrackPoint], tolerance: float = 1e-3) -> List[str]:
    """Sanity-check the frame stayed orthonormal throughout. Returns a
    list of warning strings (empty list = all good)."""
    warnings = []
    for i, p in enumerate(points):
        lf = v_length(p.front)
        ll = v_length(p.left)
        lu = v_length(p.up)
        if abs(lf - 1.0) > tolerance or abs(ll - 1.0) > tolerance or abs(lu - 1.0) > tolerance:
            warnings.append(f"Point {i} (dist {p.distance:.2f}m): frame not unit length "
                             f"(front={lf:.4f}, left={ll:.4f}, up={lu:.4f})")
        fu = abs(v_dot(p.front, p.up))
        fl = abs(v_dot(p.front, p.left))
        lu2 = abs(v_dot(p.left, p.up))
        if max(fu, fl, lu2) > tolerance:
            warnings.append(f"Point {i} (dist {p.distance:.2f}m): frame not orthogonal "
                             f"(front.up={fu:.5f}, front.left={fl:.5f}, left.up={lu2:.5f})")
    return warnings


def export_csv(points: List[TrackPoint], path: str, include_front: bool = True) -> None:
    """Write `points` to `path` in NL2's Track Spline CSV format."""
    out_path = Path(path)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(HEADER)
        for i, p in enumerate(points, start=1):
            front = p.front if include_front else [0.0, 0.0, 0.0]
            writer.writerow([
                i,
                f"{p.pos[0]:.6f}", f"{p.pos[1]:.6f}", f"{p.pos[2]:.6f}",
                f"{front[0]:.6f}", f"{front[1]:.6f}", f"{front[2]:.6f}",
                f"{p.left[0]:.6f}", f"{p.left[1]:.6f}", f"{p.left[2]:.6f}",
                f"{p.up[0]:.6f}", f"{p.up[1]:.6f}", f"{p.up[2]:.6f}",
            ])
