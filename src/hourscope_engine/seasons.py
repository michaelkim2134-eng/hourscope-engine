"""Inner Seasons (secondary progressions, solar arc) and the Birthday Chart (returns).

See docs/research/western-depth-and-timing.md (3.3-3.6).
- Secondary progressions: the sky N days after birth describes year N of life.
  Progressed JD = birth JD + (target JD - birth JD) / 365.2422.
  Progressed Moon chapters (sign changes, ~2.5 years), progressed lunar phase
  (eight 45-degree phases, ~3.7 years each), progressed Sun sign change, and
  stations of progressed Mercury, Venus and Mars.
- Solar arc: arc = progressed Sun - natal Sun, added to every natal point.
- Turning points: progressed Moon, progressed Sun and solar-arc points making
  exact major aspects (1 degree) to natal planets and angles, past two years
  and next five, flagged "echo" when the natal chart already links the pair.
- Solar return: the moment the Sun is back on its natal degree, cast for the
  current city; lunar return likewise for the Moon.
Themes and windows only, never events (see the research's section 7).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from .chart import SIGNS, BirthChart, _house_of, chart_at_utc
from .insights import TRADITIONAL_RULERS
from .sky import bisect_root, datetime_from_jd, jd_from_datetime, longitude_of
from .transits import _exact_times

YEAR = 365.2422
MOVERS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
PHASES = ["New Moon", "Crescent", "First Quarter", "Gibbous", "Full Moon", "Disseminating", "Last Quarter", "Balsamic"]


def _sep(a: float, b: float) -> float:
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def _iso(jd: float) -> str:
    return datetime_from_jd(jd).isoformat()


@dataclass
class Seasons:
    system: str
    progressed: dict
    moon_chapter: dict
    lunar_phase: dict
    sun: dict
    stations: list[dict]
    turning_points: list[dict]
    solar_return: dict | None
    lunar_return: dict | None
    warnings: list[str] = field(default_factory=list)
    moon_chapters: list[dict] = field(default_factory=list)  # every progressed Moon sign, birth to age 90

    def to_dict(self) -> dict:
        return asdict(self)


def seasons(chart: BirthChart, now: datetime, latitude: float, longitude: float, timezone_name: str) -> Seasons:
    sidereal = chart.system == "vedic"
    birth = jd_from_datetime(datetime.fromisoformat(chart.utc_time))
    t_now = jd_from_datetime(now)
    has_houses = chart.time_known and bool(chart.house_cusps)
    warnings = [] if chart.time_known else ["Birth time unknown: progressed houses, angles and return-chart houses are left out."]

    def prog_jd(t: float) -> float:
        return birth + (t - birth) / YEAR

    def prog(name: str, t: float) -> float:
        return longitude_of(name, prog_jd(t), sidereal)[0]

    def house_of(lon: float) -> int | None:
        if not has_houses:
            return None
        if sidereal and chart.ascendant is not None:
            return (int(lon // 30) - int(chart.ascendant.longitude // 30)) % 12 + 1
        return _house_of(lon, chart.house_cusps)

    def real_crossing(f, t0: float, t1: float, step: float) -> float | None:
        """First real-time moment in [t0, t1] where integer-valued f changes."""
        start = f(t0)
        t = t0
        while t < t1:
            t2 = min(t + step, t1)
            if f(t2) != start:
                return bisect_root(lambda x: 0.5 if f(x) == start else -0.5, t, t2, 1e-3)
            t = t2
        return None

    def last_crossing(f, t_end: float, span: float, step: float) -> float | None:
        cur = f(t_end)
        t = t_end
        while t > t_end - span:
            t2 = t - step
            if f(t2) != cur:
                return bisect_root(lambda x: 0.5 if f(x) != cur else -0.5, t2, t, 1e-3)
            t = t2
        return None

    # Progressed positions now.
    positions = {n: round(prog(n, t_now), 3) for n in MOVERS}
    progressed = {n: {"sign": SIGNS[int(lon // 30)], "degree": round(lon % 30, 2), "house": house_of(lon)} for n, lon in positions.items()}

    # Progressed Moon chapter (sign change ~ every 2.5 years of real time).
    moon_sign = lambda t: int(prog("Moon", t) // 30)  # noqa: E731
    began = last_crossing(moon_sign, t_now, 40 * 31, 31) or birth
    ends = real_crossing(moon_sign, t_now, t_now + 40 * 31, 31)
    moon_chapter = {
        "sign": progressed["Moon"]["sign"], "house": progressed["Moon"]["house"],
        "began": _iso(began), "ends": _iso(ends) if ends else None,
        "percent": round((t_now - began) / (ends - began) * 100, 1) if ends and ends > began else None,
        "next_sign": SIGNS[(moon_sign(t_now) + 1) % 12],
    }

    # Every progressed Moon chapter from birth to age 90, or five years past today for anyone older,
    # so the current chapter always has a real end (about 2.5 years each).
    # The crossing found sits a moment before the change, so each search starts a day past it.
    moon_chapters: list[dict] = []
    began_at, end_life = birth, birth + max(90 * YEAR, (t_now - birth) + 5 * YEAR)
    while began_at < end_life:
        probe = began_at if began_at == birth else began_at + 1
        nxt = real_crossing(moon_sign, probe, min(probe + 40 * 31, end_life), 31)
        lon0 = prog("Moon", probe)
        lon1 = prog("Moon", (nxt if nxt else min(probe + 40 * 31, end_life)) - 1)
        moon_chapters.append({
            "sign": SIGNS[int(lon0 // 30)], "house": house_of(lon0), "house_end": house_of(lon1),
            "began": _iso(began_at), "ends": _iso(nxt) if nxt else None,
            "age": round((began_at - birth) / YEAR, 1),
        })
        if not nxt:
            break
        began_at = nxt

    # Progressed lunar phase (~30-year cycle in eight steps).
    phase_of = lambda t: int(((prog("Moon", t) - prog("Sun", t)) % 360) // 45)  # noqa: E731
    p_now = phase_of(t_now)
    p_began = last_crossing(phase_of, t_now, 5 * YEAR, 31)
    p_next = real_crossing(phase_of, t_now, t_now + 5 * YEAR, 31)
    lunar_phase = {"phase": PHASES[p_now], "began": _iso(p_began) if p_began else None,
                   "next": PHASES[(p_now + 1) % 8], "next_at": _iso(p_next) if p_next else None}

    # Progressed Sun: next sign change within 31 years.
    sun_sign = lambda t: int(prog("Sun", t) // 30)  # noqa: E731
    s_next = real_crossing(sun_sign, t_now, t_now + 31 * YEAR, 120)
    sun = {"sign": progressed["Sun"]["sign"], "next_sign": SIGNS[(sun_sign(t_now) + 1) % 12],
           "next_at": _iso(s_next) if s_next else None}

    # Stations of progressed Mercury, Venus, Mars across life (one progressed day = one year).
    stations = []
    for name in ("Mercury", "Venus", "Mars"):
        prev = longitude_of(name, birth, sidereal)[1] < 0
        for age in range(1, 96):
            retro = longitude_of(name, birth + age, sidereal)[1] < 0
            if retro != prev:
                stations.append({"planet": name, "turns": "retrograde" if retro else "direct", "age": age,
                                 "at": _iso(birth + age * YEAR)})
            prev = retro

    # Turning points: progressed Moon/Sun and solar-arc points to natal planets and angles.
    natal = {p.name: p.longitude for p in chart.planets if p.name in MOVERS}
    if chart.time_known and chart.ascendant is not None:
        natal["Ascendant"] = chart.ascendant.longitude
        if chart.midheaven is not None:
            natal["Midheaven"] = chart.midheaven.longitude
    natal_pairs = {frozenset((a.a, a.b)) for a in chart.aspects}
    sun0 = natal["Sun"]

    def movers_at(t: float) -> dict[str, float]:
        arc = (prog("Sun", t) - sun0) % 360
        out = {"progressed Moon": prog("Moon", t), "progressed Sun": prog("Sun", t)}
        for n, lon in natal.items():
            if n != "Sun":
                out[f"solar arc {n}"] = (lon + arc) % 360
        return out

    samples = [t_now - 2 * YEAR + i * 30.44 for i in range(int(7 * 12) + 1)]
    series = [movers_at(t) for t in samples]
    points: list[dict] = []
    for mover in series[0]:
        base = mover.split(" ", 2)[-1] if mover.startswith("solar arc") else mover.split(" ")[1]
        for target, tlon in natal.items():
            if mover.startswith("solar arc") and target == base:
                continue
            for kind, angle in ASPECTS.items():
                orbs = [abs(_sep(s[mover], tlon) - angle) for s in series]
                for i in range(1, len(orbs) - 1):
                    if orbs[i] <= orbs[i - 1] and orbs[i] <= orbs[i + 1] and orbs[i] < 1.0:
                        points.append({"mover": mover, "kind": kind, "target": target, "at": _iso(samples[i]),
                                       "orb": round(orbs[i], 2), "echo": frozenset((base, target)) in natal_pairs,
                                       "past": samples[i] < t_now})
    order = {"Ascendant": 0, "Midheaven": 0, "Sun": 1, "Moon": 1}
    points.sort(key=lambda e: e["at"])
    # Keep it readable: at most 14, preferring angles and luminaries, then time order.
    if len(points) > 14:
        points = sorted(points, key=lambda e: (order.get(e["target"], 2), e["at"]))[:14]
        points.sort(key=lambda e: e["at"])

    # Returns, cast for the current city.
    zone = ZoneInfo(timezone_name)

    def cast(jd: float) -> BirthChart:
        return chart_at_utc(datetime_from_jd(jd), latitude, longitude, chart.system)

    def summary(rc: BirthChart, kind: str, jd: float) -> dict:
        asc = rc.ascendant
        angular = []
        if asc is not None:
            pts = {"Ascendant": asc.longitude, "Descendant": (asc.longitude + 180) % 360}
            if rc.midheaven is not None:
                pts.update({"Midheaven": rc.midheaven.longitude, "IC": (rc.midheaven.longitude + 180) % 360})
            for p in rc.planets:
                if p.name in MOVERS + ["Uranus", "Neptune", "Pluto"]:
                    for ang, lon in pts.items():
                        if _sep(p.longitude, lon) <= 5:
                            angular.append({"planet": p.name, "angle": ang})
        ruler = TRADITIONAL_RULERS[asc.sign] if asc else None
        moon = rc.planet("Moon")
        sunp = rc.planet("Sun")
        out = {
            "kind": kind, "at": _iso(jd), "ascendant": asc.sign if asc else None,
            "ascendant_in_natal_house": house_of(asc.longitude) if asc else None,
            "sun_house": sunp.house, "moon": {"sign": moon.sign, "house": moon.house},
            "ruler": ruler, "ruler_house": rc.planet(ruler).house if ruler else None, "angular": angular,
            "contacts": [{"planet": p.name, "natal": n, "orb": round(_sep(p.longitude, lon), 2)}
                         for p in rc.planets if p.name in MOVERS for n, lon in natal.items()
                         if p.name != n and _sep(p.longitude, lon) <= 2],
        }
        return out

    sr = lr = None
    try:
        sr_times = [t for t in _exact_times("Sun", sun0, 0.0, t_now - 400, t_now + 1, sidereal) if t <= t_now]
        if sr_times and sr_times[-1] - birth > 300:
            sr = summary(cast(sr_times[-1]), "solar", sr_times[-1])
            nxt = _exact_times("Sun", sun0, 0.0, t_now, t_now + 370, sidereal)
            sr["next"] = _iso(nxt[0]) if nxt else None
        moon0 = chart.planet("Moon").longitude
        lr_times: list[float] = []
        # The Moon moves ~13 degrees a day: find the last crossing with a fine search.
        t = t_now
        prev = (longitude_of("Moon", t, sidereal)[0] - moon0) % 360
        while t > t_now - 30:
            t2 = t - 0.25
            cur = (longitude_of("Moon", t2, sidereal)[0] - moon0) % 360
            if cur > prev:   # wrapped through 0 going backwards
                lr_times = [bisect_root(lambda x: ((longitude_of("Moon", x, sidereal)[0] - moon0 + 180) % 360) - 180, t2, t, 1e-5)]
                break
            prev, t = cur, t2
        if lr_times:
            lr = summary(cast(lr_times[0]), "lunar", lr_times[0])
            lr["next"] = _iso(lr_times[0] + 27.3217)
    except ValueError as e:
        warnings.append(f"Return charts unavailable: {e}")

    return Seasons(chart.system, progressed, moon_chapter, lunar_phase, sun, stations, points, sr, lr, warnings, moon_chapters)
