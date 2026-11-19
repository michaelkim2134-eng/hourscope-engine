"""Retrograde periods, with their shadow dates.

A planet "stations retrograde" when it appears to stop and move backwards,
then "stations direct" when it turns forward again. Astrologers also watch
the shadow: the pre-shadow starts when the planet first reaches the degree
where it will later station direct; the post-shadow ends when it returns to
the degree where it stationed retrograde.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .chart import SIGNS
from .sky import bisect_root, datetime_from_jd, longitude_of, signed_diff

WATCHED = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
SURVIVAL = ("Mercury", "Venus", "Mars")  # the ones Survival Mode themes


@dataclass
class Retrograde:
    planet: str
    pre_shadow_start: str
    station_retrograde: str
    station_direct: str
    post_shadow_end: str
    retrograde_longitude: float
    direct_longitude: float
    retrograde_sign: str
    direct_sign: str

    def to_dict(self) -> dict:
        return asdict(self)


def _speed(planet: str, jd: float, sidereal: bool) -> float:
    return longitude_of(planet, jd, sidereal)[1]


def _station(planet: str, a: float, b: float, sidereal: bool) -> float:
    return bisect_root(lambda t: _speed(planet, t, sidereal), a, b, 1e-5)


def _crossing(planet: str, target: float, a: float, b: float, sidereal: bool) -> float:
    return bisect_root(lambda t: signed_diff(longitude_of(planet, t, sidereal)[0], target), a, b, 1e-5)


def _find_crossing(planet: str, target: float, start: float, step: float, limit_days: float, sidereal: bool) -> float | None:
    """First time after `start` (step > 0) or before it (step < 0) the planet passes `target`, moving forward."""
    t = start
    prev = signed_diff(longitude_of(planet, t, sidereal)[0], target)
    travelled = 0.0
    while travelled < limit_days:
        t2 = t + step
        cur = signed_diff(longitude_of(planet, t2, sidereal)[0], target)
        if abs(prev) < 30 and abs(cur) < 30 and (prev <= 0 < cur or cur <= 0 < prev):
            return _crossing(planet, target, min(t, t2), max(t, t2), sidereal)
        prev, t, travelled = cur, t2, travelled + abs(step)
    return None


def retrogrades_between(jd_start: float, jd_end: float, planets: tuple[str, ...] = WATCHED, sidereal: bool = False) -> list[Retrograde]:
    """Every retrograde period that is retrograde, or in shadow, at some point in [jd_start, jd_end]."""
    out: list[Retrograde] = []
    for planet in planets:
        # Look a bit beyond the range so periods already under way are found.
        lookback = 200 if planet in ("Mercury", "Venus", "Mars") else 400
        t = jd_start - lookback
        step = 1.0
        prev = _speed(planet, t, sidereal)
        sr: float | None = None
        while t < jd_end + lookback:  # far enough ahead to find the end of periods under way
            t2 = t + step
            cur = _speed(planet, t2, sidereal)
            if prev > 0 >= cur:
                sr = _station(planet, t, t2, sidereal)
            elif prev < 0 <= cur and sr is not None:
                sd = _station(planet, t, t2, sidereal)
                sr_lon = longitude_of(planet, sr, sidereal)[0]
                sd_lon = longitude_of(planet, sd, sidereal)[0]
                pre = _find_crossing(planet, sd_lon, sr, -1.0, 120, sidereal) or sr
                post = _find_crossing(planet, sr_lon, sd, 1.0, 180, sidereal) or sd
                if post >= jd_start and pre <= jd_end:
                    out.append(Retrograde(
                        planet=planet,
                        pre_shadow_start=datetime_from_jd(pre).isoformat(),
                        station_retrograde=datetime_from_jd(sr).isoformat(),
                        station_direct=datetime_from_jd(sd).isoformat(),
                        post_shadow_end=datetime_from_jd(post).isoformat(),
                        retrograde_longitude=round(sr_lon, 3),
                        direct_longitude=round(sd_lon, 3),
                        retrograde_sign=SIGNS[int(sr_lon // 30)],
                        direct_sign=SIGNS[int(sd_lon // 30)],
                    ))
                sr = None
            prev, t = cur, t2
    out.sort(key=lambda r: r.station_retrograde)
    return out
