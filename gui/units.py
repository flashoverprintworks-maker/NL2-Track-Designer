METERS_PER_FOOT = 0.3048


def m_to_ft(value_m: float) -> float:
    return value_m / METERS_PER_FOOT


def ft_to_m(value_ft: float) -> float:
    return value_ft * METERS_PER_FOOT


def ms_to_kmh(value_ms: float) -> float:
    return value_ms * 3.6


def kmh_to_ms(value_kmh: float) -> float:
    return value_kmh / 3.6


def ms_to_mph(value_ms: float) -> float:
    return value_ms * 2.2369362921


def mph_to_ms(value_mph: float) -> float:
    return value_mph / 2.2369362921
