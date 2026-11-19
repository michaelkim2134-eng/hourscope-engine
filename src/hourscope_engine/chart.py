"""Natal chart calculation: Western (tropical) and Vedic (sidereal).

Positions come from the Swiss Ephemeris. By default it uses its built-in
Moshier model (accurate to well under an arcminute for planets, a few
arcseconds for the Moon, which is far finer than a chart needs). If the
HOURSCOPE_EPHE_PATH environment variable points at a folder of Swiss
Ephemeris data files, those are used instead.

Defaults (CLAUDE.md):
- Western: tropical zodiac, Placidus houses.
- Vedic: sidereal zodiac, Lahiri ayanamsa, Whole Sign houses, mean nodes,
  27 nakshatras with padas.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timezone
from typing import Literal

import swisseph as swe

from .places import timezone_at
from .timeconv import LocalTimeResult, local_to_utc

System = Literal["western", "vedic"]

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Vedic names for the signs (rashis), same order.
RASHIS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
# Ruling planet of each nakshatra (Vimshottari order, repeating every 9).
_NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
NAKSHATRA_SPAN = 360.0 / 27.0      # 13 deg 20 min
PADA_SPAN = NAKSHATRA_SPAN / 4.0   # 3 deg 20 min

_WESTERN_BODIES = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY), ("Venus", swe.VENUS),
    ("Mars", swe.MARS), ("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN),
    ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE), ("Pluto", swe.PLUTO),
    ("North Node", swe.MEAN_NODE),
]
_VEDIC_BODIES = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS), ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS), ("Saturn", swe.SATURN),
    ("Rahu", swe.MEAN_NODE),
]

# Western major aspects: (name, angle, orb in degrees)
ASPECTS = [
    ("conjunction", 0.0, 8.0),
    ("sextile", 60.0, 5.0),
    ("square", 90.0, 7.0),
    ("trine", 120.0, 8.0),
    ("opposition", 180.0, 8.0),
]


@dataclass
class Position:
    name: str
    longitude: float          # 0-360 in this chart's zodiac
    sign: str
    sign_degree: float        # 0-30 within the sign
    dms: str                  # e.g. "23°30' Pisces" (degrees and minutes, truncated)
    speed: float              # degrees per day
    retrograde: bool
    house: int | None = None
    rashi: str | None = None          # Vedic only
    nakshatra: str | None = None      # Vedic only
    nakshatra_lord: str | None = None
    pada: int | None = None


@dataclass
class Aspect:
    a: str
    b: str
    kind: str
    orb: float


@dataclass
class BirthChart:
    system: System
    time_known: bool
    local_time: str
    utc_time: str
    timezone: str
    time_basis: str
    latitude: float
    longitude: float
    zodiac: str
    house_system: str | None
    ayanamsa: float | None
    planets: list[Position]
    ascendant: Position | None
    midheaven: Position | None
    house_cusps: list[float] | None
    aspects: list[Aspect]
    warnings: list[str] = field(default_factory=list)
    # Extra Western points kept apart from `planets` (which the rest of the engine treats as
    # the classic planets and nodes). Today: Chiron. Empty for Vedic charts.
    points: list[Position] = field(default_factory=list)
    point_aspects: list[Aspect] = field(default_factory=list)

    def planet(self, name: str) -> Position:
        for p in self.planets:
            if p.name == name:
                return p
        raise KeyError(name)

    def to_dict(self) -> dict:
        return asdict(self)


def _norm360(x: float) -> float:
    x = math.fmod(x, 360.0)
    return x + 360.0 if x < 0 else x


def format_dms(longitude: float) -> str:
    lon = _norm360(longitude)
    sign = SIGNS[int(lon // 30)]
    within = lon % 30
    deg = int(within)
    minutes = int((within - deg) * 60 + 1e-9)
    return f"{deg}°{minutes:02d}' {sign}"


def _position(name: str, lon: float, speed: float, vedic: bool) -> Position:
    lon = _norm360(lon)
    sign_index = int(lon // 30)
    pos = Position(
        name=name,
        longitude=lon,
        sign=SIGNS[sign_index],
        sign_degree=lon % 30,
        dms=format_dms(lon),
        speed=speed,
        retrograde=speed < 0,
    )
    if vedic:
        # Count padas (108 around the circle) with a tiny tolerance so a
        # planet exactly on a boundary isn't pushed back by rounding error.
        pada_index = int(lon * 108 / 360 + 1e-9) % 108
        n = pada_index // 4
        pos.rashi = RASHIS[sign_index]
        pos.nakshatra = NAKSHATRAS[n]
        pos.nakshatra_lord = _NAKSHATRA_LORDS[n % 9]
        pos.pada = pada_index % 4 + 1
    return pos


# Chiron needs the Swiss Ephemeris asteroid file seas_18.se1 (1800-2399); the built-in
# Moshier model has no asteroids. Looked for in HOURSCOPE_EPHE_PATH, then the engine's
# ephe/ folder (development), then /app/ephe (the container). Without it Chiron is left out.
_CHIRON_FILE = "seas_18.se1"
CHIRON_ORB = 5.0  # a minor body, so tighter orbs than the planets


def _find_asteroid_path() -> str | None:
    candidates = [os.environ.get("HOURSCOPE_EPHE_PATH"), str(Path(__file__).resolve().parents[2] / "ephe"), "/app/ephe"]
    for c in candidates:
        if c and (Path(c) / _CHIRON_FILE).is_file():
            return c
    return None


_ASTEROID_PATH = _find_asteroid_path()


def chiron_available() -> bool:
    return _ASTEROID_PATH is not None


def _chiron(jd: float) -> Position | None:
    if not _ASTEROID_PATH:
        return None
    # Setting the path doesn't affect the Moshier planets, which ignore it.
    swe.set_ephe_path(_ASTEROID_PATH)
    try:
        xx, _ = swe.calc_ut(jd, swe.CHIRON, swe.FLG_SWIEPH | swe.FLG_SPEED)
    except swe.Error:
        return None  # outside the file's years
    return _position("Chiron", xx[0], xx[3], False)


def _point_aspects(points: list[Position], planets: list[Position], ascendant: Position | None, midheaven: Position | None) -> list[Aspect]:
    others = [p for p in planets if p.name != "South Node"] + [x for x in (ascendant, midheaven) if x]
    found: list[Aspect] = []
    for pt in points:
        for q in others:
            sep = abs(_norm360(pt.longitude - q.longitude))
            sep = min(sep, 360 - sep)
            for kind, angle, _orb in ASPECTS:
                if abs(sep - angle) <= CHIRON_ORB:
                    found.append(Aspect(pt.name, q.name, kind, round(abs(sep - angle), 2)))
    return found


def _ephemeris_flag() -> int:
    path = os.environ.get("HOURSCOPE_EPHE_PATH")
    if path:
        swe.set_ephe_path(path)
        return swe.FLG_SWIEPH
    return swe.FLG_MOSEPH


def _house_of(lon: float, cusps: list[float]) -> int:
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        span = _norm360(end - start)
        if _norm360(lon - start) < span:
            return i + 1
    return 12


def _aspects(planets: list[Position]) -> list[Aspect]:
    found: list[Aspect] = []
    for i, p in enumerate(planets):
        for q in planets[i + 1:]:
            if {p.name, q.name} == {"North Node", "South Node"}:
                continue  # always exactly opposite, not a real aspect
            sep = abs(_norm360(p.longitude - q.longitude))
            sep = min(sep, 360 - sep)
            for kind, angle, orb in ASPECTS:
                if abs(sep - angle) <= orb:
                    found.append(Aspect(p.name, q.name, kind, round(abs(sep - angle), 2)))
    return found


def compute_chart(
    birth_date: date,
    birth_time: time | None,
    latitude: float,
    longitude: float,
    timezone_name: str | None = None,
    system: System = "western",
    manual_utc_offset_hours: float | None = None,
) -> BirthChart:
    """Calculate a natal chart.

    birth_time=None means the time is unknown: a noon chart is used and the
    houses and Ascendant are left out (CLAUDE.md ground rule 4).
    """
    if system not in ("western", "vedic"):
        raise ValueError("system must be 'western' or 'vedic'")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude out of range")

    vedic = system == "vedic"
    time_known = birth_time is not None
    tz = timezone_name or timezone_at(latitude, longitude)
    local_t = birth_time if time_known else time(12, 0)
    conv: LocalTimeResult = local_to_utc(birth_date, local_t, tz, longitude, manual_utc_offset_hours)
    warnings = list(conv.warnings)

    u = conv.utc
    hour = u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9
    jd = swe.julday(u.year, u.month, u.day, hour, swe.GREG_CAL)

    flags = _ephemeris_flag() | swe.FLG_SPEED
    ayanamsa = None
    if vedic:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        flags |= swe.FLG_SIDEREAL
        # The 'true' ayanamsa (with nutation) is the one the sidereal positions use.
        ayanamsa = swe.get_ayanamsa_ex_ut(jd, flags)[1]

    planets: list[Position] = []
    for name, body in (_VEDIC_BODIES if vedic else _WESTERN_BODIES):
        xx, _ = swe.calc_ut(jd, body, flags)
        planets.append(_position(name, xx[0], xx[3], vedic))
    # The south node (Ketu) is always exactly opposite the north node (Rahu).
    node = planets[-1]
    planets.append(_position("Ketu" if vedic else "South Node", node.longitude + 180, node.speed, vedic))

    points: list[Position] = []
    if not vedic and (chiron := _chiron(jd)) is not None:
        points.append(chiron)

    ascendant = midheaven = None
    cusps: list[float] | None = None
    house_system: str | None = None
    if time_known:
        hsys = b"W" if vedic else b"P"
        house_system = "Whole Sign" if vedic else "Placidus"
        hflags = swe.FLG_SIDEREAL if vedic else 0
        try:
            cusp_t, ascmc = swe.houses_ex(jd, latitude, longitude, hsys, hflags)
        except swe.Error:
            # Placidus is undefined near the poles; Porphyry always works.
            cusp_t, ascmc = swe.houses_ex(jd, latitude, longitude, b"O", hflags)
            house_system = "Porphyry"
            warnings.append("Placidus houses don't work this close to the poles, so Porphyry houses were used.")
        cusps = [_norm360(c) for c in cusp_t[:12]]
        ascendant = _position("Ascendant", ascmc[0], 0.0, vedic)
        midheaven = _position("Midheaven", ascmc[1], 0.0, vedic)
        for p in planets + points:
            p.house = _house_of(p.longitude, cusps)
    else:
        warnings.append(
            "Birth time unknown: this is a noon chart. Houses and the Ascendant are hidden, "
            "and the Moon may be up to about 7 degrees off."
        )

    return BirthChart(
        system=system,
        time_known=time_known,
        local_time=f"{birth_date.isoformat()} {local_t.strftime('%H:%M:%S')}",
        utc_time=u.isoformat(),
        timezone=tz,
        time_basis=conv.time_basis,
        latitude=latitude,
        longitude=longitude,
        zodiac="sidereal (Lahiri)" if vedic else "tropical",
        house_system=house_system,
        ayanamsa=ayanamsa,
        planets=planets,
        ascendant=ascendant,
        midheaven=midheaven,
        house_cusps=cusps,
        aspects=[] if vedic else _aspects(planets),
        warnings=warnings,
        points=points,
        point_aspects=_point_aspects(points, planets, ascendant, midheaven),
    )


def chart_at_utc(moment_utc: datetime, latitude: float, longitude: float, system: System = "western") -> BirthChart:
    """A chart for an exact UTC moment at a place (relocated, return and election charts).

    Building from UTC directly avoids a local-time round trip, which can drift by
    many minutes for historical dates in local-mean-time eras (rule 3).
    """
    u = moment_utc.astimezone(timezone.utc)
    return compute_chart(u.date(), u.time().replace(microsecond=0), latitude, longitude, "UTC", system, 0.0)

