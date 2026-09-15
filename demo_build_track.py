"""
Demo: builds a small sample layout (straight -> banked turn -> hill ->
loop -> helix -> banked turn -> straight) and exports it to CSV in NL2's
Track Spline format. Run this, then in NL2: Coaster tab -> Import ->
Track Spline -> select demo_track.csv.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nl2designer.track import Track
from nl2designer import elements as el
from nl2designer.export_csv import export_csv, validate_points


def build_demo_track() -> Track:
    t = Track(name="Demo Layout", start_pos=(0, 30, 0), start_heading_deg=0, step_size=0.25)
    t.add(el.straight(20, name="Station Straight"))
    t.add(el.banked_turn(radius=25, angle_deg=90, bank_deg=45, direction="left"))
    t.add(el.straight(10))
    t.add(el.hill(radius=40, angle_deg=-25, name="Drop In"))
    t.add(el.hill(radius=60, angle_deg=25, name="Drop Out"))
    t.add(el.loop(radius=12))
    t.add(el.straight(8))
    t.add(el.helix(radius=15, num_turns=2.0, height_change=-20, bank_deg=60, direction="right"))
    t.add(el.banked_turn(radius=20, angle_deg=90, bank_deg=30, direction="left"))
    t.add(el.straight(20, name="Brake Run"))
    return t


def main():
    track = build_demo_track()
    print(track.summary())
    print()

    heartline_points = track.build()
    rail_points = track.build_rail_points()
    print(f"Generated {len(rail_points)} sample points over {rail_points[-1].distance:.1f} m of track.")
    print(f"Heartline offset: {track.heartline_offset:.2f} m "
          f"(exported rail path is offset down from the design heartline by this amount).")

    warnings = validate_points(rail_points)
    if warnings:
        print(f"\n{len(warnings)} validation warning(s):")
        for w in warnings[:10]:
            print("  " + w)
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")
    else:
        print("Validation OK: frame stayed orthonormal across the whole track.")

    # Report the height range and a rough "does it stay above ground" check,
    # since this demo track's start_pos.y = 30 is arbitrary sandbox scenery.
    min_y = min(p.pos[1] for p in rail_points)
    max_y = max(p.pos[1] for p in rail_points)
    print(f"\nHeight range (rails): {min_y:.1f} m to {max_y:.1f} m")

    out_path = Path(__file__).parent / "demo_track.csv"
    export_csv(rail_points, str(out_path))
    print(f"\nExported (rail path): {out_path}")


if __name__ == "__main__":
    main()
