"""The public sky for one day: facts for social posts that aren't about one person.

Everything a daily post can mention (Moon sign, phase and void-of-course times,
planetary hours at a reference city, planets changing sign, retrogrades and
their stations, the next new and full Moon, the universal numbers) comes from
here, so no post ever invents a date or time (rule 1).
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .chart import SIGNS
from .hours import planetary_day
from .lunar import lunations, moon_state, next_moon_ingress, void_of_course_window
from .numerology import NUMBER_THEMES, reduce_number
from .retrogrades import retrogrades_between
from .sky import bisect_root, datetime_from_jd, jd_from_datetime, longitude_of

SKY_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
SOCIAL_VERSION = "social-1"


def universal_numbers(on: date) -> dict:
    """Universal Year, Month and Day (Pythagorean, same reduction as the Personal numbers)."""
    year = reduce_number(sum(int(c) for c in str(on.year)))
    month = reduce_number(year + reduce_number(on.month))
    day = reduce_number(month + reduce_number(on.day))
    return {"year": year, "month": month, "day": day, "day_theme": NUMBER_THEMES[day]}


def illumination(elongation: float) -> float:
    """Lit fraction of the Moon's disc (0-1) from the Moon-Sun elongation."""
    return (1 - math.cos(math.radians(elongation))) / 2


def _sign_index(body: str, jd: float) -> int:
    return int(longitude_of(body, jd)[0] // 30) % 12


def _iso(jd: float, zone: ZoneInfo) -> str:
    return datetime_from_jd(jd).astimezone(zone).isoformat()


def sky_day(local_date: date, latitude: float, longitude: float, timezone_name: str, place: str | None = None) -> dict:
    zone = ZoneInfo(timezone_name)
    start = jd_from_datetime(datetime.combine(local_date, time(0, 0), tzinfo=zone))
    end = jd_from_datetime(datetime.combine(local_date + timedelta(days=1), time(0, 0), tzinfo=zone))
    noon = jd_from_datetime(datetime.combine(local_date, time(12, 0), tzinfo=zone))

    pd = planetary_day(local_date, latitude, longitude, timezone_name)
    moon = moon_state(noon)

    # Void-of-course periods that touch this local day.
    voids: list[dict] = []
    jd = start
    for _ in range(4):
        _, v_start, v_end = void_of_course_window(jd)
        if v_start < end and v_end > start:
            voids.append({"start": _iso(v_start, zone), "end": _iso(v_end, zone)})
        if v_end >= end:
            break
        jd = v_end + 1e-4

    ingress = next_moon_ingress(start)
    moon_ingress = None
    if ingress < end:
        moon_ingress = {"at": _iso(ingress, zone), "sign": SIGNS[_sign_index("Moon", ingress + 1e-3)]}

    planets = []
    for name in SKY_PLANETS:
        lon, speed = longitude_of(name, noon)
        planets.append({"name": name, "sign": SIGNS[int(lon // 30)], "degree": round(lon % 30, 2),
                        "retrograde": speed < 0})

    # Planets other than the Moon that change sign during the day.
    ingresses = []
    for name in SKY_PLANETS[2:] + ("Sun",):
        a, b = _sign_index(name, start), _sign_index(name, end)
        if a != b:
            # Moving forward it crosses the start of the new sign; moving backward, the start of the old one.
            boundary = b * 30.0 if (b - a) % 12 == 1 else a * 30.0

            def f(t: float, boundary=boundary) -> float:
                return ((longitude_of(name, t)[0] - boundary + 180) % 360) - 180

            at = bisect_root(f, start, end, 1e-6)
            ingresses.append({"planet": name, "at": _iso(at, zone), "from_sign": SIGNS[a], "to_sign": SIGNS[b]})

    # Retrogrades in effect today and stations in the next 30 days.
    retro_active, stations = [], []
    for r in retrogrades_between(start - 240, end + 30):
        sr, sd = datetime.fromisoformat(r.station_retrograde), datetime.fromisoformat(r.station_direct)
        day_start, day_end = datetime_from_jd(start), datetime_from_jd(end)
        if sr < day_end and sd > day_start:
            retro_active.append({"planet": r.planet, "sign": r.retrograde_sign, "station_retrograde": sr.astimezone(zone).isoformat(),
                                 "station_direct": sd.astimezone(zone).isoformat()})
        for kind, when, sign in (("retrograde", sr, r.retrograde_sign), ("direct", sd, r.direct_sign)):
            if day_start <= when < day_start + timedelta(days=30):
                stations.append({"planet": r.planet, "type": kind, "at": when.astimezone(zone).isoformat(), "sign": sign})
    stations.sort(key=lambda s: s["at"])

    lun = [{**x, "at": datetime.fromisoformat(x["at"]).astimezone(zone).isoformat()} for x in lunations(start, start + 31)]
    next_new = next((x for x in lun if x["type"] == "new"), None)
    next_full = next((x for x in lun if x["type"] == "full"), None)
    today_lunation = next((x for x in lun if x["at"][:10] == local_date.isoformat()), None)

    return {
        "version": SOCIAL_VERSION,
        "date": local_date.isoformat(),
        "weekday": local_date.strftime("%A"),
        "place": place,
        "timezone": timezone_name,
        "day_ruler": pd.day_ruler,
        "sunrise": pd.sunrise.isoformat(),
        "sunset": pd.sunset.isoformat(),
        "hours": [{"number": h.number, "ruler": h.ruler, "start": h.start.isoformat(), "end": h.end.isoformat(),
                   "is_day": h.is_day} for h in pd.hours],
        "moon": {
            "sign": moon.sign,
            "degree": round(moon.sign_degree, 2),
            "phase": moon.phase,
            "illumination": round(illumination(moon.elongation) * 100),
            "elongation": round(moon.elongation % 360, 2),  # 0-180 waxing, 180-360 waning
            "void_of_course": voids,
            "ingress": moon_ingress,
        },
        "planets": planets,
        "ingresses": ingresses,
        "retrogrades": retro_active,
        "stations": stations,
        "lunation_today": today_lunation,
        "next_new_moon": next_new,
        "next_full_moon": next_full,
        "numbers": universal_numbers(local_date),
        "warnings": list(pd.warnings),
    }
