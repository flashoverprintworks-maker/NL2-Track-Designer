# NL2 Track Designer — Core Engine (MVP)

## Getting started if you don't want to touch Python

**Easiest: double-click `Start NL2 Track Designer.bat`.** It installs
Python automatically if it's missing (you may need to run it twice —
once to install Python, once to launch, if Python wasn't already on
your PC), sets everything up, and opens the app. No typing required.

**Want an actual standalone .exe instead?** See `BUILD_EXE_GUIDE.md` —
a free GitHub cloud service builds a real Windows .exe for you, no
coding involved, just uploading a folder and clicking a button.

---

A from-scratch alternative to FVD++ for NoLimits 2: define a coaster as a
chain of named elements (straight, banked turn, hill, loop, helix...)
instead of hand-written force-vector formulas, and export a smooth 3D
path that NoLimits 2 can import directly.

This first milestone is the **engine**, not the GUI: the math that turns
element definitions into a valid track, plus the exporter. This is the
part that has to be correct before any drag-and-drop interface is worth
building on top of it.

## Why CSV export instead of a `.nl2elem`/`.nlelem` file?

Two "bring custom track into NL2" formats exist:

- `.nl2elem` — NL2's native element format. It's XML, but NL2's own docs
  don't publish the schema in detail, and the older binary `.nlelem`
  (from NoLimits 1) has never been publicly documented at the byte level.
  Guessing at either risked shipping something that silently corrupts or
  simply fails to import, with no way for me to test it against real NL2
  on your machine.
- **Track Spline CSV** — officially documented by NL2: 13 tab-separated
  columns (position + front/left/up orientation vectors) per point.
  Import via **Coaster tab → Import → Track Spline**. This is fully
  specified, so it's what this project targets.

Net effect for you: same outcome (your designed track becomes real,
rideable NL2 track), built on a format I could actually verify against
the spec instead of guessing.

## Project layout

```
nl2designer/
  geometry.py    - Frame math: walks an orthonormal basis along the path
                    (front/left/up), integrating pitch/yaw/roll rates.
  elements.py     - Named element library (straight, banked_turn, hill,
                    loop, helix, barrel_roll, zero_g_roll) + custom()
                    for full FVD++-style raw control.
  track.py        - Track: chains ElementSpecs end-to-end, keeping the
                    running position/orientation between elements.
  export_csv.py   - Writes NL2's Track Spline CSV format + a geometry
                    validator (checks the frame stayed orthonormal).

demo_build_track.py  - Builds a sample layout and exports demo_track.csv
```

## Running the demo

```
python3 demo_build_track.py
```

This builds a ~440 m sample layout (straight, banked turn, drop, loop,
helix, banked turn, brake run), validates the geometry, and writes
`demo_track.csv`. Import that file into NL2 via Coaster tab → Import →
Track Spline to see it as real track.

## Using it for your own layout

```python
from nl2designer.track import Track
from nl2designer import elements as el
from nl2designer.export_csv import export_csv, validate_points

t = Track(name="My Coaster", start_pos=(0, 30, 0))
t.add(el.straight(20))
t.add(el.banked_turn(radius=25, angle_deg=90, bank_deg=45, direction="left"))
t.add(el.loop(radius=12))
# ...add as many elements as you like...

points = t.build()
print(validate_points(points) or "OK")
export_csv(points, "my_coaster.csv")
```

For anything the built-in element library doesn't cover, `elements.custom()`
gives you the same raw primitives FVD++ exposes (pitch/yaw/roll change
over a given length, with optional eased ramping) without needing a
formula language — just numbers.

## GUI (milestone 2)

```
pip install -r requirements.txt
python run_gui.py
```

- **Elements panel (left)** — drag an element onto the track list, or
  double-click to append it to the end.
- **Track list (middle)** — drag to reorder. Double-click an item to
  edit its parameters (radius, angle, bank, etc. — a plain form, no
  formulas). Del key or "Remove selected" deletes an item.
- **Preview + summary (right)** — updates live: a top-down view and a
  side (height) profile, plus the same text summary and geometry
  validation the CLI demo prints.
- **Toolbar** — New / Open / Save a project as JSON, and **Export CSV
  for NL2**, which writes the Track Spline CSV and tells you where to
  import it (Coaster tab → Import → Track Spline).

Adding a new element type to the palette is a matter of adding one
entry to `gui/registry.py` (name, builder function, parameter list) —
the parameter dialog, save/load, and export all pick it up automatically.

## Heartline offset (milestone 4)

You now design along the **heartline** — the path a rider's center of
mass follows, which is what all the pitch/yaw/roll math is defined
relative to (this is also why rolls have always felt "right": rotating
around the exact point you're standing on, rather than an offset rail,
is what a heartline roll *is*). The GUI has a "Heartline offset (m)"
field next to the track name (default 1.1m, typical for a sit-down
coaster) that controls how far below that path the physical rails sit
when exported. Both previews show the heartline as a dashed reference
line alongside the solid rail path, so you can see what the offset is
actually doing — including the fact that at the inverted top of a loop,
the rails correctly end up *above* the heartline in world space, exactly
like a real coaster.

Set it to 0 if you'd rather export the heartline itself with no offset.
Locked in by two more tests in `test_geometry.py`.

## Units toggle (milestone 5)

A "Units" dropdown in the toolbar (Meters / Feet) controls how the
heartline offset field and every length/radius/height parameter in the
element edit dialog are **displayed and entered**. Angles, turn counts,
etc. are unaffected (they're unit-agnostic). Under the hood, everything
is always stored, computed, and exported in meters — NL2's file format
is metric regardless of what display units NL2 itself shows you, so
switching this toggle never changes the actual track, just how
comfortable it is to type numbers into. Verified end-to-end (toggle,
param dialog conversion, round-trip back to meters) before shipping.

**Important, unrelated to units:** Track Spline import/export in NL2
appears to be a **Professional-license feature**, not available in the
standard/Steam version. If you haven't already, check NL2's Coaster tab
→ Import → Track Spline is actually present before relying on this
tool's export path — if it's missing, we should talk before you invest
more time here.

## Real manufacturer elements (milestone 6)

The palette now includes named inversions and signature elements
researched from real manufacturers, alongside the original generic
shapes:

| Element | Manufacturer/origin | Notes |
|---|---|---|
| Immelmann | B&M | Half loop + half twist, exits reversed and upright. Named after the WW1 aerial maneuver. |
| Dive Loop | B&M | An Immelmann run in reverse order. |
| Sidewinder | Arrow/Vekoma | Half loop + half twist with an added quarter-turn of yaw, exits at ~90° instead of a full reversal. |
| Cobra Roll | B&M/Intamin | Double inversion, exits reversed and upright. **Approximation** - see `elements.py` docstring; the real element's middle section curves sideways in a way this engine simplifies. |
| Corkscrew | Arrow | The original 1975 inversion - mechanically identical to Barrel Roll with one rotation, given its own historical name. |
| Wave Turn | RMC (coined the term) | An airtime hill ridden banked a full 90°. |
| Outward Banked Turn | RMC | A turn banked *away* from the curve instead of into it - the signature "thrown outward" RMC sensation. |
| Overbanked Turn | Common across B&M/RMC/etc. | Banked Turn's math, widened to the 90-130° range that makes it an overbank rather than a normal turn. |
| Stengel Dive | Intamin/Mack (named for designer Werner Stengel) | Camelback hill that tilts past 90° at the crest, then releases back to level. |

All were checked against Coasterpedia, the Roller Coaster Wiki, and
Wikipedia's list of roller coaster elements rather than built from
memory, and each has automated regression tests in `test_geometry.py`
verifying the specific real-world claim (Immelmann/Dive Loop/Cobra Roll
exit reversed and upright; Sidewinder exits near 90°; Outward Banked
Turn genuinely mirrors a normal Banked Turn's lean; etc.) - not just
"doesn't crash."

**Not implemented, and why:** Batwing and a few of the most elaborate
interlocking inversions (Pretzel Knot, Norwegian Loop) are complex
enough 3D shapes that a faithful version would need more than this
engine's sequential pitch/yaw/roll model to get right without
guessing - they're skippable in favor of the elements above being
correct rather than having more elements that are shakier. S&S's
actual signature technology (launch towers, 4th-dimension spinning
seats) is a different degree of freedom entirely (seat rotation
independent of track path) that this track-geometry-only engine can't
represent - no element added on their behalf, rather than faking one.

## Lift hill tool (milestone 7)

Four new palette entries build a complete, correctly-heighted lift hill
in one drag: bottom transition curve, straight chain/cable run, and
crest transition back to level - all sized automatically to reach
exactly the height you specify, regardless of angle or transition
radii (`elements.lift_hill()` solves for the straight run's length
given the two transition arcs' own height contribution).

Angles are sourced from real examples rather than guessed:

| Preset | Angle | Basis |
|---|---|---|
| Classic Chain | 20-30° (default 25°) | Early/wooden-coaster chain lifts, per Coaster101's lift hill history. |
| Standard Steel/B&M | 30° | Cited explicitly as "the standard 30° lift angle" in coverage of Millennium Force's design (the angle Intamin deliberately built steeper than). |
| Intamin Cable | 45° | Millennium Force's actual, specifically-documented cable lift angle - built steeper than standard specifically to shrink the ride's footprint. |
| Vertical/Elevator | 85° | Near-vertical elevator-style lifts used on some Gerstlauer and Intamin models (e.g. Fahrenheit, Pitts Special - both documented as "vertical chain lift"). |

**A real bug this caught:** building the lift hill's height verification
surfaced a genuine sign error in the core pitch rotation that had been
present since early in this project - `hill(+angle)` was actually
descending, not climbing, the opposite of its documented behavior.
Every earlier correctness check (Immelmann exits reversed and upright,
loops close cleanly, orthonormality) happened to use pitch
symmetrically enough that the sign never got exposed - climbing and
diving by equal-and-opposite amounts, or a full 360° loop, look correct
either way. It's fixed now at the root (`geometry.py`'s
`integrate_element`), covered by a dedicated regression test
(`test_pitch_sign_convention`) so it can't silently regress again, and
it corrects the absolute up/down sense of every pitch-using element:
Hill Arc, Camelback, Zero-G Roll, Wave Turn, Stengel Dive, and the
"climb"/"dive" phases of Immelmann/Dive Loop/Sidewinder/Cobra Roll.
Nothing about their *shape* (inversions, reversals, exit angles) was
ever wrong - only which direction was "up" for a positive angle.

## Arrow Dynamics style tool (milestone 8)

Arrow Dynamics designed track by hand, before CAD, and it shows in two
specific, well-known ways: **transitions arrive abruptly** instead of
ramping in smoothly (no clothoid-style ease), and the ride has a rattly,
imprecisely-surveyed feel. Rather than one more palette element, this is
a **track-level style** - two new controls next to the heartline offset
field:

- **"Arrow Dynamics style (abrupt transitions)"** checkbox - when on,
  every element's pitch/yaw/roll transitions become constant-rate
  instead of whatever smooth profile they'd normally use. Verified
  directly: with it off, a Banked Turn's roll rate ramps up gradually
  (its first step is ~5% of its steady-state rate); with it on, the
  first step is already at ~100% of steady-state - the bank arrives all
  at once at the element boundary, exactly the "awkward transition"
  feel being asked for. Toggling it never touches your saved element
  parameters - it's a display/build-time transform, off = your original
  smooth track, unchanged.
- **"Roughness (deg)"** spinbox - layers a small, deterministic banking
  wobble onto the finished rail path, standing in for imprecise
  hand-surveying. Deterministic (same track always produces the same
  wobble - reopening a saved project won't reshuffle it), stays
  orthonormal, and is a smooth drift (sum of a few sine waves) rather
  than literal per-point noise, so it reads as imprecise rather than
  jagged/broken. 0 = off (the default everywhere).

Both persist in saved projects. Worth knowing going in: Arrow's other
signature traits are already just what this engine does by default -
circular (non-clothoid) loops, and the Corkscrew/Sidewinder elements
already carry Arrow's name and math - so combining those with the new
style toggle gets you most of the way to a period-accurate Arrow
Dynamics feel without needing anything else new.

## Example track included (milestone 9)

`examples/hydra_the_revenge.json` - a recreation of Hydra the Revenge
(B&M floorless, Dorney Park) built with this program's own elements, so
new users have something real to open and explore immediately. Open it
via **File → Open** in the app, or see `examples/README.md` for what's
accurate to the real ride vs. representative, and how the closing loop
was solved rather than guessed.

## Closure readout (milestone 10)

A new "Distance back to start" panel under the track list, directly
motivated by having to solve this by hand for the Hydra the Revenge
example: two live readouts, **ΔX / ΔY / ΔZ / straight-line distance**
between the track's starting point and (a) the very end of the track,
and (b) whichever element is currently selected in the track list -
click through your elements one at a time to watch the numbers evolve,
the same way you'd trace a path by hand to find out where a closing
turn needs to go.

Both previews also draw a short dashed red/orange guide line from the
end of the track straight back to the start, so the "which way and how
far" is visible at a glance, not just in the numbers. Composite elements
(Immelmann, Cobra Roll, Lift Hill, etc.) are handled correctly - the
readout is per *palette row*, not per flattened sub-segment, even
though those expand to 2-3 elements internally.

Respects the units toggle (feet display converts these too) and is
covered by dedicated tests: a closed loop reports ~0 offset, a plain
straight reports an offset exactly matching its own length along a
single axis, and row-based lookups are verified against composite
elements specifically.

## Speed / G-force estimation (milestone 11)

A new "Speed / G-Forces" tab charts estimated speed and G-forces along
the entire track, alongside two new controls (Start speed, Friction)
next to the Arrow-style toggle.

**The physics:** energy conservation (`v² = v0² + 2·g·Δh`, minus a
simplified friction/drag loss term) for speed, then the track's own
curvature (rate of change of the direction of travel) combined with
speed and gravity for G-forces. Verified against textbook circular-
motion formulas before shipping, not just eyeballed: a flat constant-
speed straight reads exactly 1.0G; a loop's bottom and top G-forces
match `1 + v²/(Rg)` and `v²/(Rg) - 1` to within floating-point
precision; the classic "zero-g" loop-entry speed (`v = sqrt(Rg)`)
reads ~0G at the top, as it should.

**A real physical finding the tests lock in:** for *any* circular
radius, the minimum entry speed needed to safely clear the top of a
loop is mathematically about 5.4% higher than the fastest entry the
ASTM F2291 bottom-G comfort limit (see below) allows - meaning a
perfectly circular loop can never satisfy both constraints at once, for
any size. This is exactly why real coasters use clothoid (non-circular)
loops, and it's a nice confirmation the model reflects something
physically real rather than an artifact of chosen thresholds.

**Comfort reference:** dashed lines on the chart mark ASTM F2291's
brief-peak limits (+5.5G vertical, -2.0G vertical, ±1.5G lateral,
sourced from current ASTM F2291 coverage - not invented). The model
doesn't account for duration (ASTM's real limits tighten the longer a
force is sustained), so treat warnings as "worth a second look," not a
certification.

**Honest scope note:** this is energy-conservation + curvature, not a
full rigid-body simulation - no car mass, individual wheel friction,
or speed-squared air drag. It also has no concept of a *powered* lift
or launch (chain lifts don't obey momentum/energy conservation) - if
your layout includes one, the "insufficient energy" warnings around it
are expected and correctly explain why, rather than being a bug; the
numbers become physically meaningful again once the model has enough
rolling momentum for the rest of the ride.

## Clothoid loops and undo/redo (milestone 12)

**Clothoid Loop** (new palette entry, "Clothoid Loop (Stengel-style)") -
a loop whose radius varies smoothly from wide at the bottom to narrow
at the top, the shape Werner Stengel introduced specifically because a
circular loop can't be both safe and comfortable (see milestone 11's
proof: for any radius, the minimum safe-clearance entry speed is
provably ~5.4% higher than the fastest speed the ASTM bottom-G limit
allows). Verified this actually solves the real problem, not just
approximates the shape: at the same entry speed, a clothoid loop with
the same average size measurably reduces bottom G-force compared to an
equivalent circular loop, while easily maintaining enough speed to stay
safe at the (now-tighter) top - locked in as a test, not just observed
once. Also verified the achieved bottom/top radii match what you ask
for to within 0.1m, and that requesting equal bottom/top radii
correctly degenerates back to a plain circular loop.

**Undo/redo** - toolbar buttons (enabled/disabled correctly based on
history) plus the standard Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y shortcuts.
Snapshot-based: every meaningful change (add/remove/reorder/edit an
element, or change any track-level setting) captures the full project
state, so undo/redo covers everything - not just the track list.
Opening a different project or starting a new one resets the history
rather than mixing unrelated undo stacks. Verified end-to-end through
the real GUI: add three elements, undo three times back to empty, redo
all three back, and confirm a new action after an undo correctly clears
the redo stack (standard editor semantics, not just "don't crash").

## Known limitations / next steps (updated after milestone 12)

**Fixed in milestone 3:**
- ~~Banked turns drift in height~~ — fixed. Yaw is now a rigid rotation
  of the whole frame around the true world-vertical axis (instead of the
  car's own, possibly-tilted, up axis). Rotating any vector around world
  vertical leaves its vertical component unchanged, so a turn with no
  requested pitch change now stays level, and existing bank is carried
  around a curve at constant angle instead of drifting. Locked in by
  `test_geometry.py`.
- ~~Preview is 2D only~~ — added a real 3D view (`gui/canvas3d.py`),
  tab next to the 2D one. Renders both rails (offset by track gauge),
  cross-ties (the clearest visual read on banking), a ground grid, and
  a start marker. Mouse: left-drag orbit, right-drag/Shift+drag pan,
  scroll to zoom. Built on PyOpenGL with hand-rolled projection/view
  matrices (no GLU dependency, since GLU isn't guaranteed present on
  every Windows OpenGL driver).

**Still open:**
1. **Loops/helixes are circular**, not clothoid — fine for validating
   the pipeline, but real comfortable loops taper their radius. A
   `loop_clothoid()` variant is a natural next element.
2. **Custom element *authoring* UI** (visually sculpting a brand new
   named element, rather than using the "Custom (advanced)" palette
   entry's raw pitch/yaw/roll fields) is a phase-5 item.
3. **Packaging to a standalone .exe**: see `BUILD_EXE_GUIDE.md` for the
   no-Python-needed path via GitHub's free cloud build, or run
   `pyinstaller --onefile --windowed run_gui.py` yourself if you have
   PyInstaller set up locally.
4. **No lighting/shading on the 3D track** — it's wireframe-style rails
   and ties, which reads banking clearly but won't look "solid." A
   later pass could extrude an actual tube/rail mesh with basic lighting
   if you want it to look more like a real render.
5. **Heartline offset is a single constant per track** — real coaster
   design sometimes varies the offset (or even which car type) along
   the ride. Not implemented; flag if you actually need it.

## Testing

- `python3 test_geometry.py` — regression tests for the math engine
  (level turns, loop closure, orthonormality). Run this after touching
  `geometry.py` or `elements.py`.
- `python3 smoke_test_gui.py` — headless GUI smoke test (add/remove/
  reorder elements, build, export, save/load project) using Qt's
  offscreen platform, useful for catching GUI-layer crashes without a
  display.

## Validation

`export_csv.validate_points()` checks every sampled point's front/left/up
still form a unit-length, mutually orthogonal basis (catches integration
bugs before they become a bad import). The demo currently passes clean.
