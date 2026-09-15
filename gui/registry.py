"""
Maps each element type to:
  - a friendly label
  - the builder function in nl2designer.elements
  - the list of editable parameters (for auto-generating the parameter
    dialog and for save/load)

Adding a new element to the palette is just adding an entry here, no
other GUI code needs to change.

Each parameter tuple is either:
  ("key", "float", default, min, max, step, unit_label)
  ("key", "choice", default, [options])
"""

from nl2designer import elements as el

ELEMENT_TYPES = {
    "straight": {
        "label": "Straight",
        "build": el.straight,
        "params": [
            ("length", "float", 20.0, 0.5, 1000.0, 0.5, "m"),
        ],
    },
    "flat_turn": {
        "label": "Flat Turn",
        "build": el.flat_turn,
        "params": [
            ("radius", "float", 25.0, 1.0, 500.0, 0.5, "m"),
            ("angle_deg", "float", 90.0, -360.0, 360.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "banked_turn": {
        "label": "Banked Turn",
        "build": el.banked_turn,
        "params": [
            ("radius", "float", 25.0, 1.0, 500.0, 0.5, "m"),
            ("angle_deg", "float", 90.0, -360.0, 360.0, 1.0, "deg"),
            ("bank_deg", "float", 45.0, -90.0, 90.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
            ("transition_frac", "float", 0.2, 0.05, 0.45, 0.01, ""),
        ],
    },
    "hill": {
        "label": "Hill Arc",
        "build": el.hill,
        "params": [
            ("radius", "float", 40.0, 2.0, 1000.0, 0.5, "m"),
            ("angle_deg", "float", 25.0, -180.0, 180.0, 1.0, "deg"),
        ],
    },
    "camelback": {
        "label": "Camelback Hill (airtime)",
        "build": el.camelback,
        "params": [
            ("radius", "float", 40.0, 3.0, 1000.0, 0.5, "m"),
            ("crest_angle_deg", "float", 25.0, 3.0, 89.0, 1.0, "deg"),
        ],
    },
    "loop": {
        "label": "Vertical Loop",
        "build": el.loop,
        "params": [
            ("radius", "float", 12.0, 3.0, 60.0, 0.5, "m"),
        ],
    },
    "clothoid_loop": {
        "label": "Clothoid Loop (Stengel-style)",
        "build": el.clothoid_loop,
        "params": [
            ("radius_bottom", "float", 18.0, 3.0, 80.0, 0.5, "m"),
            ("radius_top", "float", 8.0, 2.0, 60.0, 0.5, "m"),
        ],
    },
    "helix": {
        "label": "Helix",
        "build": el.helix,
        "params": [
            ("radius", "float", 15.0, 3.0, 200.0, 0.5, "m"),
            ("num_turns", "float", 2.0, 0.25, 10.0, 0.25, "turns"),
            ("height_change", "float", -20.0, -200.0, 200.0, 1.0, "m"),
            ("bank_deg", "float", 60.0, -85.0, 85.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "barrel_roll": {
        "label": "Barrel Roll",
        "build": el.barrel_roll,
        "params": [
            ("length", "float", 25.0, 2.0, 200.0, 0.5, "m"),
            ("num_rolls", "float", 1.0, 0.5, 5.0, 0.5, "rolls"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "zero_g_roll": {
        "label": "Zero-G Roll",
        "build": el.zero_g_roll,
        "params": [
            ("radius", "float", 40.0, 2.0, 300.0, 0.5, "m"),
            ("angle_deg", "float", 40.0, -180.0, 180.0, 1.0, "deg"),
            ("num_rolls", "float", 1.0, 0.5, 3.0, 0.5, "rolls"),
        ],
    },
    "custom": {
        "label": "Custom (advanced)",
        "build": el.custom,
        "params": [
            ("length", "float", 20.0, 0.5, 1000.0, 0.5, "m"),
            ("total_pitch_deg", "float", 0.0, -360.0, 360.0, 1.0, "deg"),
            ("total_yaw_deg", "float", 0.0, -360.0, 360.0, 1.0, "deg"),
            ("total_roll_deg", "float", 0.0, -360.0, 360.0, 1.0, "deg"),
            ("pitch_easing", "choice", "flat", ["flat", "eased"]),
            ("yaw_easing", "choice", "flat", ["flat", "eased"]),
            ("roll_easing", "choice", "flat", ["flat", "eased"]),
            ("transition_frac", "float", 0.2, 0.05, 0.45, 0.01, ""),
        ],
    },

    # --- Named elements from real manufacturers (see elements.py docstrings
    # for sourcing and, where relevant, approximation notes) -----------------
    "immelmann": {
        "label": "Immelmann (B&M)",
        "build": el.immelmann,
        "params": [
            ("radius", "float", 15.0, 3.0, 60.0, 0.5, "m"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "dive_loop": {
        "label": "Dive Loop (B&M)",
        "build": el.dive_loop,
        "params": [
            ("radius", "float", 15.0, 3.0, 60.0, 0.5, "m"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "sidewinder": {
        "label": "Sidewinder (Arrow/Vekoma)",
        "build": el.sidewinder,
        "params": [
            ("radius", "float", 15.0, 3.0, 60.0, 0.5, "m"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "cobra_roll": {
        "label": "Cobra Roll (B&M/Intamin)",
        "build": el.cobra_roll,
        "params": [
            ("radius", "float", 15.0, 3.0, 60.0, 0.5, "m"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "corkscrew": {
        "label": "Corkscrew (Arrow)",
        "build": el.corkscrew,
        "params": [
            ("length", "float", 25.0, 2.0, 200.0, 0.5, "m"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "wave_turn": {
        "label": "Wave Turn (RMC)",
        "build": el.wave_turn,
        "params": [
            ("radius", "float", 30.0, 3.0, 300.0, 0.5, "m"),
            ("angle_deg", "float", 40.0, -180.0, 180.0, 1.0, "deg"),
            ("bank_deg", "float", 90.0, 10.0, 100.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "outward_banked_turn": {
        "label": "Outward Banked Turn (RMC)",
        "build": el.outward_banked_turn,
        "params": [
            ("radius", "float", 25.0, 3.0, 300.0, 0.5, "m"),
            ("angle_deg", "float", 60.0, -360.0, 360.0, 1.0, "deg"),
            ("bank_deg", "float", 45.0, 10.0, 90.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
            ("transition_frac", "float", 0.2, 0.05, 0.45, 0.01, ""),
        ],
    },
    "overbanked_turn": {
        "label": "Overbanked Turn",
        "build": el.banked_turn,  # same math as Banked Turn - just a wider, RMC/B&M-typical bank range
        "params": [
            ("radius", "float", 25.0, 3.0, 300.0, 0.5, "m"),
            ("angle_deg", "float", 90.0, -360.0, 360.0, 1.0, "deg"),
            ("bank_deg", "float", 105.0, 91.0, 130.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
            ("transition_frac", "float", 0.2, 0.05, 0.45, 0.01, ""),
        ],
    },
    "stengel_dive": {
        "label": "Stengel Dive (Intamin/Mack)",
        "build": el.stengel_dive,
        "params": [
            ("radius", "float", 40.0, 5.0, 300.0, 0.5, "m"),
            ("hill_angle_deg", "float", 35.0, 5.0, 80.0, 1.0, "deg"),
            ("turn_angle_deg", "float", 60.0, -180.0, 180.0, 1.0, "deg"),
            ("bank_deg", "float", 110.0, 91.0, 150.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },
    "treble_clef_turn": {
        "label": "Treble Clef Turn (B&M/Fury 325)",
        "build": el.treble_clef_turn,
        "params": [
            ("radius", "float", 70.0, 15.0, 300.0, 1.0, "m"),
            ("total_turn_deg", "float", 200.0, 90.0, 270.0, 5.0, "deg"),
            ("dive_deg", "float", 20.0, 5.0, 40.0, 1.0, "deg"),
            ("bank_deg", "float", 60.0, 20.0, 85.0, 1.0, "deg"),
            ("direction", "choice", "left", ["left", "right"]),
        ],
    },

    # --- Lift hills, styled after real manufacturer angles -------------------
    # All four share the same underlying builder (elements.lift_hill) - just
    # different default angle/transition-radius presets. See lift_hill()'s
    # docstring for the sourcing behind each angle.
    "lift_classic": {
        "label": "Lift Hill - Classic Chain (20-30\u00b0)",
        "build": el.lift_hill,
        "params": [
            ("height", "float", 25.0, 3.0, 200.0, 1.0, "m"),
            ("angle_deg", "float", 25.0, 15.0, 35.0, 1.0, "deg"),
            ("bottom_transition_radius", "float", 10.0, 3.0, 60.0, 0.5, "m"),
            ("top_transition_radius", "float", 14.0, 3.0, 60.0, 0.5, "m"),
        ],
    },
    "lift_standard_steel": {
        "label": "Lift Hill - Standard Steel/B&M (30\u00b0)",
        "build": el.lift_hill,
        "params": [
            ("height", "float", 40.0, 3.0, 250.0, 1.0, "m"),
            ("angle_deg", "float", 30.0, 25.0, 35.0, 1.0, "deg"),
            ("bottom_transition_radius", "float", 12.0, 3.0, 60.0, 0.5, "m"),
            ("top_transition_radius", "float", 18.0, 3.0, 60.0, 0.5, "m"),
        ],
    },
    "lift_cable_intamin": {
        "label": "Lift Hill - Intamin Cable (45\u00b0)",
        "build": el.lift_hill,
        "params": [
            ("height", "float", 90.0, 5.0, 320.0, 1.0, "m"),
            ("angle_deg", "float", 45.0, 35.0, 60.0, 1.0, "deg"),
            ("bottom_transition_radius", "float", 15.0, 3.0, 60.0, 0.5, "m"),
            ("top_transition_radius", "float", 20.0, 3.0, 60.0, 0.5, "m"),
        ],
    },
    "lift_vertical": {
        "label": "Lift Hill - Vertical/Elevator (85\u00b0)",
        "build": el.lift_hill,
        "params": [
            ("height", "float", 45.0, 5.0, 200.0, 1.0, "m"),
            ("angle_deg", "float", 85.0, 60.0, 89.0, 1.0, "deg"),
            ("bottom_transition_radius", "float", 8.0, 2.0, 40.0, 0.5, "m"),
            ("top_transition_radius", "float", 8.0, 2.0, 40.0, 0.5, "m"),
        ],
    },
}


def default_params(type_key: str) -> dict:
    """A fresh params dict with default values for a given element type."""
    spec = ELEMENT_TYPES[type_key]
    out = {}
    for p in spec["params"]:
        key, kind = p[0], p[1]
        out[key] = p[2]  # default is always the 3rd entry
    return out


def build_element(type_key: str, params: dict, name: str = ""):
    """Call the real element builder with the given params, returning an
    ElementSpec. `name` overrides the auto-generated element name if set."""
    spec = ELEMENT_TYPES[type_key]
    kwargs = dict(params)
    if name:
        kwargs["name"] = name
    return spec["build"](**kwargs)
