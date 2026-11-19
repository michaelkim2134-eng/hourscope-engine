"""The sky over time, and the big moments in it for one person.

- sky_frames: planet positions at regular steps (for the Living Wheel and Time Scrubber).
- transit_events: exact transits of the slow planets to the person's key points,
  planetary returns, eclipses, retrograde stations, sign changes of the slow
  planets, and (Vedic) dasha changes. Each comes with an importance from 1 to 3.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

import swisseph as swe

from .chart import SIGNS, BirthChart, _house_of
from .insights import TRADITIONAL_RULERS, vimshottari
from .retrogrades import retrogrades_between
from .sky import bisect_root, datetime_from_jd, ephe_flag, longitude_of, signed_diff

FRAME_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
SLOW = ["Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
EVENT_ASPECTS = {"conjunction": 0.0, "square": 90.0, "trine": 120.0, "opposition": 180.0}


def sky_frames(jd_start: float, days: int, step_hours: float = 24, sidereal: bool = False) -> list[dict]:
    """Positions (longitude, speed) of the ten planets at regular steps."""
    frames = []
    steps = int(days * 24 / step_hours) + 1
    for k in range(steps):
        jd = jd_start + k * step_hours / 24
        planets = []
        for name in FRAME_PLANETS:
            lon, speed = longitude_of(name, jd, sidereal)
            planets.append({"name": name, "lon": round(lon, 4), "speed": round(speed, 5)})
        frames.append({"at": datetime_from_jd(jd).isoformat(), "planets": planets})
    return frames


@dataclass
class TransitEvent:
    at: str
    kind: str          # transit, return, eclipse, station, ingress, dasha
    title: str
    detail: str
    planets: list[str]
    importance: int    # 1 (notable) to 3 (major)

    def to_dict(self) -> dict:
        return asdict(self)


def _exact_times(planet: str, target_lon: float, angle: float, jd0: float, jd1: float, sidereal: bool) -> list[float]:
    """Times in [jd0, jd1] when `planet` is exactly `angle` degrees from a fixed point (either side)."""
    targets = {angle, -angle} if angle not in (0.0, 180.0) else {angle}
    times = []
    step = 1.0 if planet != "Mars" else 0.5
    for tgt in targets:
        t = jd0
        prev = signed_diff(longitude_of(planet, t, sidereal)[0] - target_lon, tgt)
        while t < jd1:
            t2 = min(t + step, jd1)
            cur = signed_diff(longitude_of(planet, t2, sidereal)[0] - target_lon, tgt)
            if abs(prev) < 20 and abs(cur) < 20 and (prev <= 0 < cur or cur <= 0 < prev):
                times.append(bisect_root(
                    lambda x, tgt=tgt: signed_diff(longitude_of(planet, x, sidereal)[0] - target_lon, tgt), t, t2, 1e-5))
            prev, t = cur, t2
    return sorted(times)


def _key_points(chart: BirthChart) -> dict[str, float]:
    pts = {"Sun": chart.planet("Sun").longitude, "Moon": chart.planet("Moon").longitude}
    if chart.ascendant is not None:
        pts["Ascendant"] = chart.ascendant.longitude
    if chart.midheaven is not None:
        pts["Midheaven"] = chart.midheaven.longitude
    ruler = TRADITIONAL_RULERS[(chart.ascendant or chart.planet("Sun")).sign]
    if ruler not in ("Sun", "Moon"):
        pts[f"{ruler} (chart ruler)"] = chart.planet(ruler).longitude
    return pts


def transit_events(chart: BirthChart, jd_start: float, days: int) -> list[TransitEvent]:
    sidereal = chart.system == "vedic"
    jd_end = jd_start + days
    events: list[TransitEvent] = []
    points = _key_points(chart)

    def house_note(lon: float) -> str:
        return f" in your house {_house_of(lon, chart.house_cusps)}" if chart.house_cusps else ""

    # 1. Slow planets aspecting your key points.
    for planet in SLOW:
        for point, plon in points.items():
            for kind, angle in EVENT_ASPECTS.items():
                if planet == "Mars" and kind == "trine":
                    continue  # keep Mars to the hard-hitting aspects
                for t in _exact_times(planet, plon, angle, jd_start, jd_end, sidereal):
                    major = kind in ("conjunction", "opposition") and point in ("Sun", "Moon", "Ascendant")
                    imp = 3 if major and planet != "Mars" else 2 if planet != "Mars" else 1
                    events.append(TransitEvent(
                        datetime_from_jd(t).isoformat(), "transit",
                        f"{planet} {kind} your {point}",
                        f"Transiting {planet} is exactly {kind} your natal {point}.",
                        [planet, point.split(" ")[0]], imp,
                    ))

    # 1b. Chiron (Western charts): slow planets meeting it, and the Chiron return (around age 50).
    chiron = next((p for p in chart.points if p.name == "Chiron"), None)
    if chiron is not None:
        for planet in ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"):
            for kind in ("conjunction", "square", "opposition"):
                for t in _exact_times(planet, chiron.longitude, EVENT_ASPECTS[kind], jd_start, jd_end, sidereal):
                    events.append(TransitEvent(
                        datetime_from_jd(t).isoformat(), "transit", f"{planet} {kind} your Chiron",
                        f"Transiting {planet} is exactly {kind} your natal Chiron{house_note(chiron.longitude)}.",
                        [planet, "Chiron"], 2,
                    ))
        try:
            for t in _exact_times("Chiron", chiron.longitude, 0.0, jd_start, jd_end, sidereal):
                events.append(TransitEvent(datetime_from_jd(t).isoformat(), "return", "Chiron return",
                                           "Chiron returns to its place in your birth chart, about 50 years after you were born.", ["Chiron"], 3))
        except ValueError:
            pass  # outside the asteroid file's years

    # 2. Returns: the Sun (birthday), Jupiter and Saturn coming back to where they were.
    for planet, imp in (("Sun", 2), ("Jupiter", 3), ("Saturn", 3)):
        natal = chart.planet(planet).longitude
        for t in _exact_times(planet, natal, 0.0, jd_start, jd_end, sidereal):
            title = "Solar return: your astrological birthday" if planet == "Sun" else f"{planet} return"
            events.append(TransitEvent(datetime_from_jd(t).isoformat(), "return", title,
                                       f"{planet} returns to its place in your birth chart.", [planet], imp))

    # 3. Eclipses, with where they land in your chart.
    flag = ephe_flag()
    t = jd_start
    while True:
        _, tret = swe.sol_eclipse_when_glob(t, flag)
        if tret[0] > jd_end:
            break
        lon = longitude_of("Sun", tret[0], sidereal)[0]
        events.append(TransitEvent(datetime_from_jd(tret[0]).isoformat(), "eclipse", f"Solar eclipse in {SIGNS[int(lon // 30)]}",
                                   f"A new-Moon eclipse at {lon % 30:.0f}° {SIGNS[int(lon // 30)]}{house_note(lon)}: a powerful fresh start.",
                                   ["Sun", "Moon"], 3))
        t = tret[0] + 20
    t = jd_start
    while True:
        _, tret = swe.lun_eclipse_when(t, flag)
        if tret[0] > jd_end:
            break
        lon = longitude_of("Moon", tret[0], sidereal)[0]
        events.append(TransitEvent(datetime_from_jd(tret[0]).isoformat(), "eclipse", f"Lunar eclipse in {SIGNS[int(lon // 30)]}",
                                   f"A full-Moon eclipse at {lon % 30:.0f}° {SIGNS[int(lon // 30)]}{house_note(lon)}: a culmination or release.",
                                   ["Moon", "Sun"], 3))
        t = tret[0] + 20

    # 4. Retrograde stations.
    for r in retrogrades_between(jd_start, jd_end, sidereal=sidereal):
        for at, word in ((r.station_retrograde, "retrograde"), (r.station_direct, "direct")):
            when = datetime.fromisoformat(at)
            if jd_start <= swe.julday(when.year, when.month, when.day, when.hour + when.minute / 60) <= jd_end:
                events.append(TransitEvent(at, "station", f"{r.planet} stations {word}",
                                           f"{r.planet} turns {word} in {r.retrograde_sign if word == 'retrograde' else r.direct_sign}.",
                                           [r.planet], 2 if r.planet in ("Mercury", "Venus", "Mars") else 1))

    # 5. Slow planets changing sign.
    for planet in ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"):
        t = jd_start
        prev = int(longitude_of(planet, t, sidereal)[0] // 30)
        while t < jd_end:
            t2 = min(t + 2, jd_end)
            cur = int(longitude_of(planet, t2, sidereal)[0] // 30)
            if cur != prev:
                exact = bisect_root(lambda x, p=prev: 0.5 if int(longitude_of(planet, x, sidereal)[0] // 30) == p else -0.5, t, t2, 1e-5)
                events.append(TransitEvent(datetime_from_jd(exact).isoformat(), "ingress", f"{planet} enters {SIGNS[cur]}",
                                           f"{planet} moves into {SIGNS[cur]}, changing the background tone for everyone.", [planet],
                                           2 if planet in ("Jupiter", "Saturn") else 1))
            prev, t = cur, t2

    # 6. Vedic: dasha and antardasha changes.
    if sidereal:
        birth = datetime.fromisoformat(chart.utc_time)
        periods, _ = vimshottari(chart.planet("Moon").longitude, birth)
        start_iso = datetime_from_jd(jd_start).date().isoformat()
        end_iso = datetime_from_jd(jd_end).date().isoformat()
        for p in periods:
            if start_iso <= p.start <= end_iso:
                events.append(TransitEvent(f"{p.start}T00:00:00+00:00", "dasha", f"{p.lord} mahadasha begins",
                                           f"A new major life period ruled by {p.lord}.", [p.lord], 3))
            for s in p.sub_periods:
                if start_iso <= s.start <= end_iso:
                    events.append(TransitEvent(f"{s.start}T00:00:00+00:00", "dasha", f"{p.lord}-{s.lord} period begins",
                                               f"A sub-period of {s.lord} within your {p.lord} dasha.", [s.lord], 2))

    events.sort(key=lambda e: e.at)
    return events


# ---------------------------------------------------------------- Life Rewind
REWIND_ORBS = {"Sun": 1.5, "Mercury": 1.5, "Venus": 1.5, "Mars": 2.0, "Jupiter": 3.0, "Saturn": 3.0,
               "Uranus": 3.0, "Neptune": 3.0, "Pluto": 3.0}
REWIND_TARGETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
SLOW_WEIGHT = {"Pluto": 6, "Neptune": 5, "Uranus": 5, "Saturn": 5, "Jupiter": 4, "Mars": 2, "Sun": 1, "Venus": 1, "Mercury": 1}


def sky_on(chart: BirthChart, birth_date, when) -> dict:
    """What the sky was doing on a date, compared with this birth chart (midday UTC)."""
    from datetime import time as dtime, timezone as dtz

    from .lunar import phase_of
    from .numerology import personal_year

    sidereal = chart.system == "vedic"
    moment = datetime.combine(when, dtime(12, 0), tzinfo=dtz.utc)
    jd = swe.julday(moment.year, moment.month, moment.day, 12.0)
    natal = {name: chart.planet(name).longitude for name in REWIND_TARGETS}
    if chart.ascendant is not None:
        natal["Ascendant"] = chart.ascendant.longitude
    if chart.midheaven is not None:
        natal["Midheaven"] = chart.midheaven.longitude

    transits = []
    positions = []
    for planet, orb in REWIND_ORBS.items():
        lon, speed = longitude_of(planet, jd, sidereal)
        positions.append({"planet": planet, "sign": SIGNS[int(lon // 30)], "retrograde": speed < 0 and planet != "Sun",
                          "house": _house_of(lon, chart.house_cusps) if chart.house_cusps else None})
        for target, tlon in natal.items():
            if planet == target and planet in ("Sun", "Mercury", "Venus"):
                continue  # these return every year; not meaningful here
            d = abs(signed_diff(lon, tlon))
            for kind, angle in EVENT_ASPECTS.items():
                exact = abs(d - angle)
                if exact <= orb:
                    transits.append({"planet": planet, "kind": kind, "target": target, "orb": round(exact, 2),
                                     "weight": SLOW_WEIGHT[planet] * (2 if kind in ("conjunction", "opposition") else 1)
                                               * (1.5 if target in ("Sun", "Moon", "Ascendant") else 1)})
    transits.sort(key=lambda t: (-t["weight"], t["orb"]))

    eclipses = []
    flag = ephe_flag()
    for finder, label in ((swe.sol_eclipse_when_glob, "solar"), (swe.lun_eclipse_when, "lunar")):
        for backwards in (True, False):
            _, tret = finder(jd, flag, 0, backwards)
            if abs(tret[0] - jd) <= 21:
                body = "Sun" if label == "solar" else "Moon"
                lon = longitude_of(body, tret[0], sidereal)[0]
                eclipses.append({"type": label, "at": datetime_from_jd(tret[0]).isoformat(), "sign": SIGNS[int(lon // 30)],
                                 "days_from": round(tret[0] - jd)})

    elong = (longitude_of("Moon", jd)[0] - longitude_of("Sun", jd)[0]) % 360
    out = {
        "date": when.isoformat(),
        "transits": transits[:8],
        "positions": positions,
        "retrogrades": [p["planet"] for p in positions if p["retrograde"]],
        "eclipses": eclipses,
        "moon_phase": phase_of(elong),
        "moon_sign": SIGNS[int(longitude_of("Moon", jd, sidereal)[0] // 30)],
        "personal_year": personal_year(birth_date, when.year),
        "dasha": None,
    }
    if sidereal:
        _, current = vimshottari(chart.planet("Moon").longitude, datetime.fromisoformat(chart.utc_time), moment)
        out["dasha"] = {k: current.get(k) for k in ("mahadasha", "antardasha")}
    return out
