"""
Test track: a 250 ft (76.2 m) B&M hyper coaster, out-and-back layout,
with a Fury 325-style Treble Clef turnaround, a mid-course brake run,
and 8 non-inverting airtime moments (Camelback Hills) - a spec-built
example rather than a recreation of a specific real ride, using the
program's real, sourced elements throughout: B&M's own 30 degree
standard chain lift angle, the Treble Clef turn (see elements.py for
its Fury 325 sourcing), and Camelback Hills of progressively decreasing
size after the first drop, matching how real B&M hypers taper their
airtime hills over the course of a ride.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.registry import build_element
from gui.project_io import save_project
from nl2designer.track import Track
from nl2designer.export_csv import export_csv, validate_points

FEET_TO_M = 0.3048
HEIGHT_M = 250.0 * FEET_TO_M  # 76.2 m

ITEMS = [
    ("straight", "Station exit", {"length": 15.0}),
    ("lift_standard_steel", "Lift Hill (250 ft)", {
        "height": HEIGHT_M, "angle_deg": 30.0, "bottom_transition_radius": 14.0, "top_transition_radius": 20.0,
    }),
    ("hill", "First Drop (dive in, 75 deg)", {"radius": 50.0, "angle_deg": -75.0}),
    ("hill", "First Drop (pull out)", {"radius": 60.0, "angle_deg": 75.0}),

    ("camelback", "Airtime Hill 1", {"radius": 60.0, "crest_angle_deg": 30.0}),
    ("banked_turn", "High-speed turn (out leg)", {
        "radius": 90.0, "angle_deg": 35.0, "bank_deg": 45.0, "direction": "right", "transition_frac": 0.25,
    }),
    ("camelback", "Airtime Hill 2", {"radius": 55.0, "crest_angle_deg": 27.0}),
    ("camelback", "Airtime Hill 3", {"radius": 50.0, "crest_angle_deg": 25.0}),

    ("treble_clef_turn", "Treble Clef Turn (far turnaround)", {
        "radius": 75.0, "total_turn_deg": 195.0, "dive_deg": 20.0, "bank_deg": 62.0, "direction": "right",
    }),

    ("camelback", "Airtime Hill 4", {"radius": 45.0, "crest_angle_deg": 22.0}),
    ("overbanked_turn", "Overbanked Turn (return leg)", {
        "radius": 50.0, "angle_deg": 40.0, "bank_deg": 100.0, "direction": "left", "transition_frac": 0.3,
    }),
    ("camelback", "Airtime Hill 5", {"radius": 40.0, "crest_angle_deg": 20.0}),

    ("straight", "Mid-Course Brake Run", {"length": 35.0}),

    ("camelback", "Airtime Hill 6", {"radius": 35.0, "crest_angle_deg": 18.0}),
    ("banked_turn", "Return-leg turn", {
        "radius": 60.0, "angle_deg": 30.0, "bank_deg": 40.0, "direction": "left", "transition_frac": 0.25,
    }),
    ("camelback", "Airtime Hill 7", {"radius": 30.0, "crest_angle_deg": 15.0}),
    # Closing sequence: solved (not guessed) the same way as the Hydra
    # example - traced exact position/heading after Airtime Hill 7,
    # computed the precise bearing back to the station, and sized this
    # turn + straight to close the out-and-back loop for real.
    ("banked_turn", "Final approach turn", {
        "radius": 55.0, "angle_deg": 51.2, "bank_deg": 35.0, "direction": "right", "transition_frac": 0.3,
    }),
    ("straight", "Return straight", {"length": 263.0}),
    ("camelback", "Airtime Hill 8 (final pop)", {"radius": 22.0, "crest_angle_deg": 12.0}),

    ("straight", "Final Brake Run", {"length": 35.0}),
    ("straight", "Return to Station", {"length": 15.0}),
]

HEARTLINE_OFFSET = 1.1


def build_track() -> Track:
    track = Track(name="Test B&M Hyper (250ft)", heartline_offset=HEARTLINE_OFFSET)
    for type_key, name, params in ITEMS:
        track.add(build_element(type_key, params, name))
    return track


def main():
    track = build_track()
    print(track.summary())
    print()

    rail = track.build_rail_points()
    warnings = validate_points(rail)
    print(f"{len(rail)} sample points, {rail[-1].distance:.1f} m total.")
    print(f"Validation: {'OK' if not warnings else f'{len(warnings)} warning(s)'}")

    min_y = min(p.pos[1] for p in rail)
    max_y = max(p.pos[1] for p in rail)
    print(f"Height range: {min_y:.1f} m to {max_y:.1f} m  (target height: {HEIGHT_M:.1f} m / 250 ft)")

    closure = track.closure_offset(rail)
    print(f"Closure: dx={closure['dx']:.1f} dy={closure['dy']:.1f} dz={closure['dz']:.1f} "
          f"dist={closure['distance']:.1f} (out of {rail[-1].distance:.1f} m total)")

    airtime_count = sum(1 for _, name, _ in ITEMS if name.startswith("Airtime Hill"))
    print(f"Airtime moments (Camelback Hills): {airtime_count}")

    out_dir = Path(__file__).parent
    csv_path = out_dir / "test_bm_hyper.csv"
    export_csv(rail, str(csv_path))
    print(f"\nExported CSV (for direct NL2 import): {csv_path}")

    project_path = out_dir / "test_bm_hyper.json"
    save_project(str(project_path), track.name, [
        {"type": t, "name": n, "params": p} for t, n, p in ITEMS
    ], HEARTLINE_OFFSET, False, 0.0, 2.0, 0.02)
    print(f"Saved GUI project (File -> Open in the app): {project_path}")


if __name__ == "__main__":
    main()
