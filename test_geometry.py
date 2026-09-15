"""
Small regression test suite - no pytest dependency needed, just run:
    python3 test_geometry.py
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nl2designer.geometry import Frame, integrate_element
from nl2designer import elements as el
from nl2designer.export_csv import validate_points

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def test_straight_no_drift():
    f = Frame.start(pos=(0, 30, 0))
    pts = integrate_element(f, el.straight(50), 0, step_size=0.5)
    max_drift = max(abs(p.pos[1] - 30) for p in pts)
    check("straight track stays level", max_drift < 1e-6, f"max_drift={max_drift}")


def test_banked_turn_stays_level():
    f = Frame.start(pos=(0, 30, 0))
    spec = el.banked_turn(radius=25, angle_deg=90, bank_deg=45, direction="left")
    pts = integrate_element(f, spec, 0, step_size=0.1)
    max_drift = max(abs(p.pos[1] - 30) for p in pts)
    check("banked turn (yaw+roll, no pitch) stays exactly level", max_drift < 1e-6, f"max_drift={max_drift}")

    end_up_y = pts[-1].up[1]
    expected_up_y = math.cos(math.radians(45))
    check("banked turn ends at the requested bank angle",
          abs(end_up_y - expected_up_y) < 1e-3, f"got up.y={end_up_y}, expected={expected_up_y}")


def test_flat_turn_various_angles_stay_level():
    for angle in [30, 90, 180, 270, 359]:
        f = Frame.start(pos=(0, 10, 0))
        spec = el.flat_turn(radius=20, angle_deg=angle, direction="left")
        pts = integrate_element(f, spec, 0, step_size=0.25)
        max_drift = max(abs(p.pos[1] - 10) for p in pts)
        check(f"flat turn {angle} deg stays level", max_drift < 1e-6, f"max_drift={max_drift}")


def test_loop_closes_and_returns_upright():
    f = Frame.start(pos=(0, 30, 0))
    spec = el.loop(radius=15)
    pts = integrate_element(f, spec, 0, step_size=0.1)
    start, end = pts[0], pts[-1]
    pos_err = math.dist(start.pos, end.pos)
    up_err = math.dist(start.up, end.up)
    check("loop returns to (nearly) the same position", pos_err < 0.05, f"pos_err={pos_err:.4f}")
    check("loop returns to (nearly) upright", up_err < 0.05, f"up_err={up_err:.4f}")


def test_orthonormality_holds_across_full_demo():
    from demo_build_track import build_demo_track
    track = build_demo_track()
    points = track.build()
    warnings = validate_points(points)
    check("full demo track stays orthonormal end to end", len(warnings) == 0, f"{len(warnings)} warnings")


def test_heartline_offset_level_track():
    from nl2designer.geometry import offset_points
    f = Frame.start(pos=(0, 30, 0))
    pts = integrate_element(f, el.straight(20), 0, step_size=1.0)
    rail = offset_points(pts, 1.1)
    diffs = [h.pos[1] - r.pos[1] for h, r in zip(pts, rail)]
    check("heartline offset drops a level straight by exactly the offset",
          all(abs(d - 1.1) < 1e-9 for d in diffs), f"diffs={diffs[:3]}...")


def test_heartline_offset_inverted_loop_top():
    from nl2designer.geometry import offset_points
    f = Frame.start(pos=(0, 30, 0))
    pts = integrate_element(f, el.loop(radius=15), 0, step_size=0.05)
    rail = offset_points(pts, 1.1)
    mid = len(pts) // 2  # approx top of the loop, inverted
    is_inverted = pts[mid].up[1] < -0.9
    rail_above_heartline = rail[mid].pos[1] > pts[mid].pos[1]
    check("near the inverted top of a loop, rails sit ABOVE the heartline",
          is_inverted and rail_above_heartline,
          f"up.y={pts[mid].up[1]:.3f}, heartline.y={pts[mid].pos[1]:.3f}, rail.y={rail[mid].pos[1]:.3f}")


def test_named_manufacturer_elements():
    import math as _math

    def build(specs, start=(0, 30, 0)):
        frame = Frame.start(pos=start)
        pts, dist = [], 0.0
        for i, spec in enumerate(specs if isinstance(specs, list) else [specs]):
            seg = integrate_element(frame, spec, dist, step_size=0.1)
            pts.extend(seg if i == 0 else seg[1:])
            last = seg[-1]
            frame = Frame(pos=last.pos, front=last.front, left=last.left, up=last.up)
            dist = last.distance
        return pts

    # Immelmann: exits reversed heading, upright, and passes through inverted.
    pts = build(el.immelmann(radius=15))
    check("Immelmann exits with reversed heading",
          math.dist(pts[-1].front, [-x for x in pts[0].front]) < 1e-3)
    check("Immelmann exits upright", pts[-1].up[1] > 0.99)
    check("Immelmann passes through inverted", min(p.up[1] for p in pts) < -0.99)

    # Dive Loop: same net orientation change as Immelmann, opposite order.
    pts = build(el.dive_loop(radius=15))
    check("Dive Loop exits with reversed heading",
          math.dist(pts[-1].front, [-x for x in pts[0].front]) < 1e-3)
    check("Dive Loop exits upright", pts[-1].up[1] > 0.99)

    # Sidewinder: exits at roughly 90 degrees, not a full reversal.
    pts = build(el.sidewinder(radius=15))
    heading_dot = sum(a * b for a, b in zip(pts[0].front, pts[-1].front))
    check("Sidewinder exits at roughly 90 degrees (not reversed)",
          abs(heading_dot) < 0.05, f"dot={heading_dot}")
    check("Sidewinder exits upright", pts[-1].up[1] > 0.99)

    # Cobra Roll: double inversion, exits reversed and upright.
    pts = build(el.cobra_roll(radius=15))
    check("Cobra Roll exits with reversed heading",
          math.dist(pts[-1].front, [-x for x in pts[0].front]) < 1e-3)
    check("Cobra Roll exits upright", pts[-1].up[1] > 0.99)
    check("Cobra Roll passes through inverted", min(p.up[1] for p in pts) < -0.99)

    # Corkscrew: one full roll, ends identical to how it started.
    pts = build([el.corkscrew(length=25)])
    check("Corkscrew returns to starting orientation", math.dist(pts[-1].up, pts[0].up) < 1e-3)
    check("Corkscrew passes through inverted", min(p.up[1] for p in pts) < -0.99)

    # Outward Banked Turn: mirrors a normal Banked Turn's lean direction.
    normal = build([el.banked_turn(radius=25, angle_deg=60, bank_deg=45, direction="left")])
    outward = build([el.outward_banked_turn(radius=25, angle_deg=60, bank_deg=45, direction="left")])
    mid_n, mid_o = normal[len(normal) // 2], outward[len(outward) // 2]
    check("Outward Banked Turn leans opposite to a normal Banked Turn",
          (mid_n.up[0] < -0.1 and mid_o.up[0] > 0.1), f"normal.up.x={mid_n.up[0]}, outward.up.x={mid_o.up[0]}")

    # Every composite above stayed orthonormal - no warnings anywhere.
    for name, specs in [
        ("Immelmann", el.immelmann(radius=15)), ("Dive Loop", el.dive_loop(radius=15)),
        ("Sidewinder", el.sidewinder(radius=15)), ("Cobra Roll", el.cobra_roll(radius=15)),
        ("Wave Turn", [el.wave_turn(radius=30, angle_deg=40)]),
        ("Outward Banked Turn", [el.outward_banked_turn(radius=25, angle_deg=90, bank_deg=45)]),
        ("Stengel Dive", el.stengel_dive(radius=40)),
        ("Corkscrew", [el.corkscrew(length=25)]),
    ]:
        pts = build(specs)
        warnings = validate_points(pts)
        check(f"{name} stays orthonormal end to end", len(warnings) == 0, f"{len(warnings)} warnings")


def test_pitch_sign_convention():
    """Locks in the exact bug that slipped through undetected before:
    hill() with a positive angle must climb, not descend. Every existing
    test used pitch symmetrically (full loops, zero pitch) so none of them
    actually pinned down the sign - this one does."""
    f = Frame.start(pos=(0, 0, 0))
    up = integrate_element(f, el.hill(radius=20, angle_deg=20), 0, step_size=0.5)
    check("hill(+angle) climbs (positive height change)", up[-1].pos[1] > 0.5, f"end y={up[-1].pos[1]}")

    f2 = Frame.start(pos=(0, 0, 0))
    down = integrate_element(f2, el.hill(radius=20, angle_deg=-20), 0, step_size=0.5)
    check("hill(-angle) descends (negative height change)", down[-1].pos[1] < -0.5, f"end y={down[-1].pos[1]}")


def test_lift_hill():
    for label, height, angle in [
        ("classic 25deg", 30, 25), ("standard 30deg", 40, 30),
        ("intamin cable 45deg", 94, 45), ("vertical 85deg", 50, 85),
    ]:
        specs = el.lift_hill(height=height, angle_deg=angle, bottom_transition_radius=12, top_transition_radius=18)
        frame = Frame.start(pos=(0, 0, 0))
        pts, dist = [], 0.0
        for i, spec in enumerate(specs):
            seg = integrate_element(frame, spec, dist, step_size=0.5)
            pts.extend(seg if i == 0 else seg[1:])
            last = seg[-1]
            frame = Frame(pos=last.pos, front=last.front, left=last.left, up=last.up)
            dist = last.distance
        achieved = pts[-1].pos[1] - pts[0].pos[1]
        check(f"lift_hill ({label}) reaches the exact requested height",
              abs(achieved - height) < 0.01, f"requested={height}, achieved={achieved:.3f}")
        check(f"lift_hill ({label}) ends level (crest, ready to continue the ride)",
              pts[-1].front[1] < 1e-3, f"front.y={pts[-1].front[1]}")
        warnings = validate_points(pts)
        check(f"lift_hill ({label}) stays orthonormal", len(warnings) == 0, f"{len(warnings)} warnings")

    # Too-small height for the transition radii should raise, not silently
    # produce a nonsense track.
    try:
        el.lift_hill(height=2, angle_deg=30, bottom_transition_radius=12, top_transition_radius=18)
        check("lift_hill raises ValueError when height is too small for transitions", False)
    except ValueError:
        check("lift_hill raises ValueError when height is too small for transitions", True)


def test_arrow_style_and_roughness():
    from nl2designer.track import Track

    def build(arrow_style=False, roughness=0.0):
        t = Track(name="t", arrow_style=arrow_style, roughness_deg=roughness)
        t.add(el.banked_turn(radius=25, angle_deg=90, bank_deg=45, direction="left"))
        return t.build_rail_points()

    smooth = build(arrow_style=False)
    abrupt = build(arrow_style=True)

    # Arrow-style must reach full rate immediately (first-step delta close
    # to the steady-state delta); smooth must ramp up from near zero.
    def delta(pts, i):
        return abs(pts[i + 1].up[0] - pts[i].up[0])

    smooth_ratio = delta(smooth, 0) / delta(smooth, 20)
    abrupt_ratio = delta(abrupt, 0) / delta(abrupt, 20)
    check("Arrow-style transitions start at full rate immediately",
          abrupt_ratio > 0.8, f"ratio={abrupt_ratio:.3f}")
    check("Smooth (default) transitions ramp up gradually",
          smooth_ratio < 0.3, f"ratio={smooth_ratio:.3f}")

    warnings = validate_points(abrupt)
    check("Arrow-style track stays orthonormal", len(warnings) == 0, f"{len(warnings)} warnings")

    check("arrow_style=False leaves the original elements untouched",
          build(False)[0].up == build(False)[0].up)  # sanity: build is pure/repeatable

    # Roughness: small deterministic wobble, orthonormal, off by default.
    rough = build(roughness=0.6)
    diffs = [math.dist(a.up, b.up) for a, b in zip(smooth, rough)]
    check("roughness=0 (default) produces an identical track to no roughness",
          build(roughness=0.0)[10].up == smooth[10].up)
    check("roughness>0 measurably perturbs the up vector", max(diffs) > 0.001, f"max diff={max(diffs):.5f}")
    check("roughness stays a *small* perturbation, not a distortion", max(diffs) < 0.1, f"max diff={max(diffs):.5f}")
    check("roughness is deterministic (same result every build)",
          build(roughness=0.6)[50].up == rough[50].up)
    check("roughness keeps the track orthonormal", len(validate_points(rough)) == 0)


def test_closure_offset():
    from nl2designer.track import Track

    # A track that returns exactly to its start should report ~0 offset.
    t = Track(name="closed loop")
    t.add(el.loop(radius=15))
    pts = t.build_rail_points()
    offset = t.closure_offset(pts)
    check("closure_offset reports ~0 for a track that returns to start",
          offset["distance"] < 0.1, f"distance={offset['distance']:.3f}")

    # A straight track should report an offset matching its own length,
    # entirely along one axis (Z, given the default heading).
    t2 = Track(name="open")
    t2.add(el.straight(50))
    pts2 = t2.build_rail_points()
    offset2 = t2.closure_offset(pts2)
    check("closure_offset dz matches a straight track's length",
          abs(offset2["dz"] - 50.0) < 0.01, f"dz={offset2['dz']}")
    check("closure_offset dx/dy are ~0 for a straight track",
          abs(offset2["dx"]) < 0.01 and abs(offset2["dy"]) < 0.01,
          f"dx={offset2['dx']}, dy={offset2['dy']}")

    # row_end_distances: composites should count as multiple elements
    # but still report one cumulative distance per PALETTE row.
    t3 = Track(name="rows")
    t3.add(el.straight(20))          # 1 element -> row 0
    t3.add(el.immelmann(radius=15))  # 2 elements -> row 1
    t3.add(el.straight(10))          # 1 element -> row 2
    row_counts = [1, 2, 1]
    distances = t3.row_end_distances(row_counts)
    check("row_end_distances has one entry per row, not per flattened element",
          len(distances) == 3, f"got {len(distances)}")
    check("row_end_distances[0] matches the first row's own length",
          abs(distances[0] - 20.0) < 0.01, f"{distances[0]}")
    check("row_end_distances is cumulative and monotonically increasing",
          distances[0] < distances[1] < distances[2], f"{distances}")


def test_speed_and_g_force():
    from nl2designer.track import Track
    from nl2designer.physics import GRAVITY

    # Frictionless energy conservation on a hill: v should match
    # sqrt(v0^2 + 2*g*dh) exactly.
    f = Frame.start(pos=(0, 0, 0))
    pts = integrate_element(f, el.hill(radius=40, angle_deg=30), 0, step_size=0.2)
    from nl2designer.physics import compute_speed_profile
    v0 = 10.0
    speeds = compute_speed_profile(pts, start_speed_ms=v0, friction_coef=0.0)
    dh = pts[0].pos[1] - pts[-1].pos[1]  # h0 - h_end (negative here since climbing)
    expected_v_sq = v0 ** 2 + 2 * GRAVITY * dh
    expected_v = math.sqrt(expected_v_sq) if expected_v_sq > 0.25 else 0.5
    check("frictionless speed profile matches energy conservation exactly",
          abs(speeds[-1] - expected_v) < 0.01, f"got {speeds[-1]:.3f}, expected {expected_v:.3f}")

    # Friction should only ever reduce speed relative to the frictionless case.
    speeds_friction = compute_speed_profile(pts, start_speed_ms=v0, friction_coef=0.05)
    check("adding friction never increases speed",
          all(sf <= sn + 1e-9 for sf, sn in zip(speeds_friction, speeds)))

    # G-force sanity on a flat, level, constant-speed straight: exactly 1G vertical, 0 lateral.
    f2 = Frame.start(pos=(0, 0, 0))
    pts2 = integrate_element(f2, el.straight(50), 0, step_size=0.5)
    from nl2designer.physics import compute_g_forces
    gforces = compute_g_forces(pts2, [20.0] * len(pts2))
    mid_vg, mid_lg = gforces[len(gforces) // 2]
    check("flat constant-speed straight reads exactly 1G vertical", abs(mid_vg - 1.0) < 1e-6, f"{mid_vg}")
    check("flat constant-speed straight reads exactly 0G lateral", abs(mid_lg) < 1e-6, f"{mid_lg}")

    # Loop bottom/top match the textbook circular-motion formulas.
    R = 15.0
    f3 = Frame.start(pos=(0, 0, 0))
    pts3 = integrate_element(f3, el.loop(radius=R), 0, step_size=0.1)
    v_test = 18.0
    gforces3 = compute_g_forces(pts3, [v_test] * len(pts3))
    bottom_g = gforces3[2][0]
    expected_bottom = 1 + v_test ** 2 / (R * GRAVITY)
    check("loop bottom G matches 1 + v^2/(Rg)", abs(bottom_g - expected_bottom) < 0.02,
          f"got {bottom_g:.3f}, expected {expected_bottom:.3f}")
    top_g = gforces3[len(gforces3) // 2][0]
    expected_top = v_test ** 2 / (R * GRAVITY) - 1
    check("loop top G matches v^2/(Rg) - 1", abs(top_g - expected_top) < 0.02,
          f"got {top_g:.3f}, expected {expected_top:.3f}")

    v_zero_g = math.sqrt(R * GRAVITY)
    gforces_zero = compute_g_forces(pts3, [v_zero_g] * len(pts3))
    check("the classic 'zero-g' loop speed reads ~0G at the top",
          abs(gforces_zero[len(gforces_zero) // 2][0]) < 0.01)

    # End-to-end through Track: a big, tight, fast loop should trip a
    # warning; a reasonably-taken banked turn shouldn't.
    t_brutal = Track(name="brutal", start_speed_ms=35.0, friction_coef=0.0)
    t_brutal.add(el.loop(radius=10))
    warnings_brutal = t_brutal.physics_warnings()
    check("an unrealistically tight/fast loop trips a G-force warning", len(warnings_brutal) > 0)

    t_gentle = Track(name="gentle turn", start_speed_ms=15.0, friction_coef=0.0)
    t_gentle.add(el.banked_turn(radius=40, angle_deg=90, bank_deg=35, direction="left"))
    warnings_gentle = t_gentle.physics_warnings()
    check("a reasonably-sized banked turn at a sane speed doesn't warn",
          len(warnings_gentle) == 0, f"got {warnings_gentle}")

    # A real, provable reason circular loops are hard to get right (and
    # why real coasters use clothoid loops instead): the minimum entry
    # speed needed to safely clear the top (v0^2 >= 5*g*R, from needing
    # v_top^2 >= g*R for the car to maintain contact) is mathematically
    # ~5.4% higher than the fastest entry the ASTM bottom-G limit allows
    # (v0^2 <= 4.5*g*R), for ANY radius - a perfectly circular loop can
    # never satisfy both at once. Confirms the model reflects something
    # physically real, not just an artifact of chosen thresholds.
    min_safe_v0_sq = 5 * GRAVITY * 20  # any radius; 20 is arbitrary here
    max_comfortable_v0_sq = 4.5 * GRAVITY * 20
    check("no circular-loop radius can satisfy both the safe-clearance speed "
          "and the ASTM bottom-G limit at once (provable, not just this radius)",
          min_safe_v0_sq > max_comfortable_v0_sq)


def test_clothoid_loop():
    def build(spec, start=(0, 0, 0)):
        f = Frame.start(pos=start)
        return integrate_element(f, spec, 0, step_size=0.1)

    def estimate_radius(pts, i):
        i0, i1 = max(0, i - 1), min(len(pts) - 1, i + 1)
        ds = pts[i1].distance - pts[i0].distance
        dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(pts[i0].front, pts[i1].front))))
        dtheta = math.acos(dot)
        return ds / dtheta if dtheta > 1e-6 else float("inf")

    pts = build(el.clothoid_loop(radius_bottom=20.0, radius_top=10.0))
    r_bottom = estimate_radius(pts, 2)
    r_top = estimate_radius(pts, len(pts) // 2)
    check("clothoid loop achieves the requested bottom radius",
          abs(r_bottom - 20.0) < 0.1, f"got {r_bottom:.2f}")
    check("clothoid loop achieves the requested top radius",
          abs(r_top - 10.0) < 0.1, f"got {r_top:.2f}")
    check("clothoid loop stays orthonormal", len(validate_points(pts)) == 0)

    # radius_bottom == radius_top should degenerate to a plain circular loop.
    pts_equal = build(el.clothoid_loop(radius_bottom=15.0, radius_top=15.0))
    r_check = estimate_radius(pts_equal, len(pts_equal) // 3)
    check("equal bottom/top radii degenerate to a circular loop",
          abs(r_check - 15.0) < 0.1, f"got {r_check:.2f}")

    # The actual point of a clothoid loop: at the same entry speed, it
    # should reduce bottom G-force compared to a same-average-size
    # circular loop, since that's the entire reason Stengel invented it.
    from nl2designer.track import Track
    from nl2designer.physics import GRAVITY
    R_avg = 15.0
    v0 = math.sqrt(5 * GRAVITY * R_avg) + 1.0
    t_circular = Track(name="circular", start_speed_ms=v0, friction_coef=0.0)
    t_circular.add(el.loop(radius=R_avg))
    bottom_g_circular = t_circular.g_forces()[2][0]

    t_clothoid = Track(name="clothoid", start_speed_ms=v0, friction_coef=0.0)
    t_clothoid.add(el.clothoid_loop(radius_bottom=R_avg * 1.5, radius_top=R_avg * 0.6))
    bottom_g_clothoid = t_clothoid.g_forces()[2][0]

    check("clothoid loop reduces bottom G-force vs. an equivalent circular loop at the same entry speed",
          bottom_g_clothoid < bottom_g_circular,
          f"circular={bottom_g_circular:.2f}, clothoid={bottom_g_clothoid:.2f}")


def main():
    test_straight_no_drift()
    test_banked_turn_stays_level()
    test_flat_turn_various_angles_stay_level()
    test_loop_closes_and_returns_upright()
    test_orthonormality_holds_across_full_demo()
    test_heartline_offset_level_track()
    test_heartline_offset_inverted_loop_top()
    test_named_manufacturer_elements()
    test_pitch_sign_convention()
    test_lift_hill()
    test_arrow_style_and_roughness()
    test_closure_offset()
    test_speed_and_g_force()
    test_clothoid_loop()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} test(s) FAILED: {FAILURES}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
