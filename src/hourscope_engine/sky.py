"""Small helpers for "where is everything right now" and sunrise/sunset.

All times are Julian days in Universal Time (jd_ut) unless named otherwise.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import swisseph as swe

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
}


def ephe_flag() -> int:
    path = os.environ.get("HOURSCOPE_EPHE_PATH")
    if path:
        swe.set_ephe_path(path)
        return swe.FLG_SWIEPH
    return swe.FLG_MOSEPH


def jd_from_datetime(dt: datetime) -> float:
    """Timezone-aware datetime -> Julian day (UT)."""
    u = dt.astimezone(timezone.utc)
    hour = u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9
    return swe.julday(u.year, u.month, u.day, hour, swe.GREG_CAL)


def datetime_from_jd(jd_ut: float) -> datetime:
    """Julian day (UT) -> timezone-aware UTC datetime (to the second)."""
    y, m, d, h = swe.revjul(jd_ut, swe.GREG_CAL)
    seconds = round(h * 3600)
    base = datetime(y, m, d, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds)


def longitude_of(body: str, jd_ut: float, sidereal: bool = False) -> tuple[float, float]:
    """(ecliptic longitude, speed in deg/day) of a body. Chiron needs the asteroid file (see chart.py)."""
    if body == "Chiron":
        from .chart import _ASTEROID_PATH  # local import: chart doesn't import sky, but keep it lazy
        if not _ASTEROID_PATH:
            raise ValueError("Chiron needs the Swiss Ephemeris asteroid file seas_18.se1")
        swe.set_ephe_path(_ASTEROID_PATH)
        cflags = swe.FLG_SWIEPH | swe.FLG_SPEED
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            cflags |= swe.FLG_SIDEREAL
        xx, _ = swe.calc_ut(jd_ut, swe.CHIRON, cflags)
        return xx[0] % 360, xx[3]
    flags = ephe_flag() | swe.FLG_SPEED
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flags |= swe.FLG_SIDEREAL
    xx, _ = swe.calc_ut(jd_ut, PLANET_IDS[body], flags)
    return xx[0] % 360, xx[3]


def _rise_or_set(jd_start: float, lat: float, lon: float, which: int) -> float | None:
    res, tret = swe.rise_trans(jd_start, swe.SUN, which, (lon, lat, 0.0), 0.0, 0.0, ephe_flag())
    if res != 0:
        return None  # Sun doesn't rise/set (polar day or night)
    return tret[0]


def next_sunrise(jd_start: float, lat: float, lon: float) -> float | None:
    """Next sunrise after jd_start: upper edge of the Sun on the horizon, with refraction."""
    return _rise_or_set(jd_start, lat, lon, swe.CALC_RISE)


def next_sunset(jd_start: float, lat: float, lon: float) -> float | None:
    return _rise_or_set(jd_start, lat, lon, swe.CALC_SET)


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def signed_diff(a: float, b: float) -> float:
    """a - b folded into (-180, 180]."""
    d = (a - b) % 360
    return d - 360 if d > 180 else d


def bisect_root(f, lo: float, hi: float, tol: float = 1e-6) -> float:
    """Find t in [lo, hi] where f changes sign (f(lo) and f(hi) differ in sign)."""
    flo = f(lo)
    for _ in range(60):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm <= 0) == (flo <= 0):
            lo, flo = mid, fm
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2


__all__ = [
    "PLANET_IDS", "angle_diff", "bisect_root", "datetime_from_jd", "jd_from_datetime",
    "longitude_of", "next_sunrise", "next_sunset", "signed_diff",
]
