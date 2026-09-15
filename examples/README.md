# Example: Hydra the Revenge (Dorney Park)

A recreation of Hydra the Revenge (Bolliger & Mabillard floorless coaster,
Dorney Park, opened 2005), built with this program's own elements so it
opens, edits, and re-exports exactly like anything you'd build yourself.

## Try it

In the app: **Open** → `examples/hydra_the_revenge.json`

Or import `examples/hydra_the_revenge.csv` directly into NL2 (Coaster
tab → Import → Track Spline) without opening the GUI at all.

## What's accurate, and what isn't

**Accurate to the real ride** (sourced from Wikipedia, Coasterpedia, and
ride reviews - not guessed):
- The full element sequence in the documented order: JoJo Roll (a
  heartline/barrel roll taken *before* the lift - unusual, and Hydra's
  signature quirk) → lift hill → first drop → canyon-hugging turns →
  inclined dive loop → zero-g roll → corkscrew → cobra roll → more
  turns and an airtime hill → second corkscrew → closing turns → brakes.
- Real figures: 95 ft (29 m) lift height, 105 ft (32 m) first drop at
  68 degrees, B&M's standard 30-degree chain lift angle, 7 inversions
  (JoJo Roll, Dive Loop, Zero-G Roll, Corkscrew, Cobra Roll counting as
  2, Corkscrew again).
- Total length: 1084 m built vs. 975 m real - close, not exact.

**Not accurate - representative instead:**
- This is not a survey/GPS-accurate recreation of the actual Allentown
  terrain or exact track coordinates - that data isn't available to
  build from, and a from-scratch recreation would need it. It's built
  as a correctly-ordered, correctly-specced layout using this program's
  elements, closed back to (approximately) the starting point the same
  way a real designer iterates on closing turns in CAD - see
  `build_hydra_the_revenge.py` for exactly how the closing sweep was
  solved (not guessed) to bring the circuit back near the station.
- The exact turn angles/radii connecting each named element (the
  "canyon race" turns, the connectors between inversions) are
  reasonable approximations, not the real ride's exact geometry.

## Rebuilding it

`python3 build_hydra_the_revenge.py` regenerates both the `.json`
project and the `.csv` export from the element list at the top of that
script - useful as a template if you want to build your own recreation
of a real coaster using the same approach (research the real element
sequence and stats, then translate it into this program's palette).
