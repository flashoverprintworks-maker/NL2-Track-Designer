"""
Builds an example recreation of Hydra the Revenge (Dorney Park, B&M
floorless coaster, opened 2005) using this program's own element
registry - i.e. built exactly the way a user would, through the same
palette entries, so the saved project opens and edits normally in the
GUI.

Sourced element sequence (Wikipedia's "Hydra the Revenge" article,
Coasterpedia, and a couple of ride reviews - not guessed):
  station -> JoJo Roll (heartline/barrel roll, taken slowly, PRE-lift -
    a genuinely unusual choice; most coasters put their first inversion
    after the drop) -> turn -> lift hill (95 ft / 29 m) -> first drop
    (105 ft / 32 m at 68 degrees, curving right) -> canyon-hugging turns
    -> inclined dive loop -> zero-g roll -> corkscrew #1 -> cobra roll
    (the signature element, counts as 2 of the ride's 7 inversions) ->
    upward left turn -> downward right turn -> airtime hill ->
    corkscrew #2 -> 360 degree left turn -> banked 90 degree right turn
    -> brake run -> station.

Honest scope note: this matches the real element SEQUENCE and the
documented height/drop/angle figures. It is not a survey-accurate
recreation of the actual Allentown terrain/coordinates (I don't have
that data, and NL2's coordinate placement for a from-scratch recreation
would need it) - it's built as a representative, correctly-ordered
layout using this program's own elements, which is what the program can
actually verify and is honest about producing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.registry import build_element
from gui.project_io import save_project
from nl2designer.track import Track
from nl2designer.export_csv import export_csv, validate_points


# (type_key, display_name, params) - identical shape to what the GUI's
# track list stores per row, so this is exactly what "File -> Open" on
# the saved project produces.
ITEMS = [
    ("corkscrew", "JoJo Roll (pre-lift heartline roll)", {"length": 18.0, "direction": "left"}),
    ("flat_turn", "Turn to lift", {"radius": 20.0, "angle_deg": 100.0, "direction": "right"}),
    ("lift_standard_steel", "Lift Hill (95 ft)", {
        "height": 29.0, "angle_deg": 30.0, "bottom_transition_radius": 12.0, "top_transition_radius": 16.0,
    }),
    ("hill", "First Drop (dive in, 68 deg)", {"radius": 42.0, "angle_deg": -68.0}),
    ("flat_turn", "First Drop (curve right)", {"radius": 35.0, "angle_deg": 20.0, "direction": "right"}),
    ("hill", "First Drop (pull out)", {"radius": 55.0, "angle_deg": 68.0}),
    ("flat_turn", "Canyon race turn 1", {"radius": 30.0, "angle_deg": 35.0, "direction": "left"}),
    ("flat_turn", "Canyon race turn 2", {"radius": 30.0, "angle_deg": 35.0, "direction": "right"}),
    ("dive_loop", "Inclined Dive Loop", {"radius": 20.0, "direction": "left"}),
    ("straight", "Connector", {"length": 10.0}),
    ("zero_g_roll", "Zero-G Roll", {"radius": 30.0, "angle_deg": 60.0, "num_rolls": 1.0}),
    ("straight", "Connector", {"length": 10.0}),
    ("corkscrew", "Corkscrew 1", {"length": 25.0, "direction": "left"}),
    ("straight", "Connector", {"length": 15.0}),
    ("cobra_roll", "Cobra Roll (signature element)", {"radius": 18.0, "direction": "right"}),
    ("straight", "Connector", {"length": 10.0}),
    ("banked_turn", "Upward left turn", {
        "radius": 30.0, "angle_deg": 60.0, "bank_deg": 35.0, "direction": "left", "transition_frac": 0.25,
    }),
    ("banked_turn", "Downward right turn", {
        "radius": 30.0, "angle_deg": 60.0, "bank_deg": 35.0, "direction": "right", "transition_frac": 0.25,
    }),
    ("hill", "Airtime hill (up)", {"radius": 35.0, "angle_deg": 22.0}),
    ("hill", "Airtime hill (down)", {"radius": 35.0, "angle_deg": -22.0}),
    ("corkscrew", "Corkscrew 2", {"length": 25.0, "direction": "right"}),
    # Closing sequence: sweeps the layout back to the station. The real
    # ride's documented "360 degree left turn, banked 90 degree right
    # turn" was the starting point here, but since I don't have Dorney
    # Park's actual survey/terrain data, the exact return routing is my
    # own approximation - these angles/radii were solved (not guessed)
    # to actually close the circuit back near the start, the same way a
    # real designer iterates on the closing turns in CAD.
    ("flat_turn", "Return sweep (left)", {"radius": 50.0, "angle_deg": -180.0, "direction": "left"}),
    ("straight", "Return straight", {"length": 196.7}),
    ("banked_turn", "Final approach turn", {
        "radius": 25.0, "angle_deg": 55.0, "bank_deg": 20.0, "direction": "right", "transition_frac": 0.25,
    }),
    ("straight", "Brake run", {"length": 20.0}),
]

HEARTLINE_OFFSET = 1.1  # meters - B&M floorless cars, standard sit-down-ish offset


def build_track() -> Track:
    track = Track(name="Hydra the Revenge (recreation)", heartline_offset=HEARTLINE_OFFSET)
    for type_key, name, params in ITEMS:
        track.add(build_element(type_key, params, name))
    return track


def main():
    track = build_track()
    print(track.summary())
    print()

    heartline = track.build()
    rail = track.build_rail_points()
    warnings = validate_points(rail)
    print(f"{len(rail)} sample points, {rail[-1].distance:.1f} m total "
          f"(real Hydra is 975 m - this is a representative layout, not a survey match).")
    print(f"Validation: {'OK' if not warnings else f'{len(warnings)} warning(s)'}")

    min_y = min(p.pos[1] for p in rail)
    max_y = max(p.pos[1] for p in rail)
    print(f"Height range: {min_y:.1f} m to {max_y:.1f} m")

    out_dir = Path(__file__).parent
    csv_path = out_dir / "hydra_the_revenge.csv"
    export_csv(rail, str(csv_path))
    print(f"\nExported CSV (for direct NL2 import): {csv_path}")

    project_path = out_dir / "hydra_the_revenge.json"
    save_project(str(project_path), track.name, [
        {"type": t, "name": n, "params": p} for t, n, p in ITEMS
    ], HEARTLINE_OFFSET, False, 0.0)
    print(f"Saved GUI project (File -> Open in the app): {project_path}")


if __name__ == "__main__":
    main()
