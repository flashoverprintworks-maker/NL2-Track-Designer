import json


def save_project(path: str, track_name: str, items: list, heartline_offset: float = 1.1,
                  arrow_style: bool = False, roughness_deg: float = 0.0,
                  start_speed_ms: float = 2.0, friction_coef: float = 0.02) -> None:
    """`items` is a list of dicts: {"type": str, "name": str, "params": dict}"""
    data = {
        "track_name": track_name,
        "items": items,
        "heartline_offset": heartline_offset,
        "arrow_style": arrow_style,
        "roughness_deg": roughness_deg,
        "start_speed_ms": start_speed_ms,
        "friction_coef": friction_coef,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_project(path: str) -> tuple:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return (
        data.get("track_name", "Untitled Track"),
        data.get("items", []),
        data.get("heartline_offset", 1.1),
        data.get("arrow_style", False),
        data.get("roughness_deg", 0.0),
        data.get("start_speed_ms", 2.0),
        data.get("friction_coef", 0.02),
    )
