"""Deeper facts about a natal chart, for detailed readings.

Everything here is derived by rule from the chart's positions (rule 1):
- Western: element/modality balance, dignities, chart patterns, house rulers,
  Part of Fortune, birth Moon phase, day/night chart.
- Vedic: Vimshottari dasha periods, navamsa (D9) signs, common yogas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import combinations

from .chart import SIGNS, BirthChart, Position, _house_of, _norm360

ELEMENT = {s: e for s, e in zip(SIGNS, ["fire", "earth", "air", "water"] * 3)}
MODALITY = {s: m for s, m in zip(SIGNS, ["cardinal", "fixed", "mutable"] * 4)}

TRADITIONAL_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}
EXALTATION = {"Sun": "Aries", "Moon": "Taurus", "Mercury": "Virgo", "Venus": "Pisces",
              "Mars": "Capricorn", "Jupiter": "Cancer", "Saturn": "Libra"}
CLASSICAL = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

# Weights for the balance: the "big three" count double.
_BALANCE_WEIGHT = {"Sun": 2, "Moon": 2, "Ascendant": 2}
_BALANCE_BODIES = CLASSICAL + ["Uranus", "Neptune", "Pluto"]


def _opposite(sign: str) -> str:
    return SIGNS[(SIGNS.index(sign) + 6) % 12]


# ---------------------------------------------------------------- Vedic dignity
# Parashara (BPHS, Rao): deep exaltation degrees (debilitation is the opposite
# degree) and moolatrikona ranges. Vedic astrology has no "detriment".
DEEP_EXALTATION = {"Sun": 10.0, "Moon": 33.0, "Mars": 298.0, "Mercury": 165.0,
                   "Jupiter": 95.0, "Venus": 357.0, "Saturn": 200.0}
MOOLATRIKONA = {"Sun": ("Leo", 0, 20), "Moon": ("Taurus", 3, 30), "Mars": ("Aries", 0, 12),
                "Mercury": ("Virgo", 15, 20), "Jupiter": ("Sagittarius", 0, 10),
                "Venus": ("Libra", 0, 15), "Saturn": ("Aquarius", 0, 20)}
# Parts of a sign where exaltation gives way to moolatrikona/own sign.
_EXALT_LIMIT = {"Moon": 3.0, "Mercury": 15.0}
DEEP_ORB = 1.0  # within 1 degree of the exact point counts as "deep"


def vedic_dignity(planet: str, longitude: float) -> str | None:
    """deep exaltation / exaltation / moolatrikona / own sign / debilitation / deep debilitation."""
    if planet not in DEEP_EXALTATION:
        return None
    lon = _norm360(longitude)
    sign = SIGNS[int(lon // 30)]
    deg = lon % 30
    exact = DEEP_EXALTATION[planet]
    if sign == EXALTATION[planet] and deg < _EXALT_LIMIT.get(planet, 30.0):
        return "deep exaltation" if _sep(lon, exact) <= DEEP_ORB else "exaltation"
    mt_sign, lo, hi = MOOLATRIKONA[planet]
    if sign == mt_sign and lo <= deg < hi:
        return "moolatrikona"
    if TRADITIONAL_RULERS[sign] == planet:
        return "own sign"
    if sign == _opposite(EXALTATION[planet]):
        return "deep debilitation" if _sep(lon, _norm360(exact + 180)) <= DEEP_ORB else "debilitation"
    return None


# Natural friendship (Parashara): enemies of each planet.
NATURAL_ENEMIES = {"Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"},
                   "Mercury": {"Moon"}, "Jupiter": {"Mercury", "Venus"},
                   "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"}}
# Combustion orbs from the Sun (BPHS); retrograde Mercury and Venus use the smaller value.
COMBUSTION_ORB = {"Moon": 12.0, "Mars": 17.0, "Mercury": 14.0, "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0}
COMBUSTION_ORB_RETRO = {"Mercury": 12.0, "Venus": 8.0}


def is_combust(planet: Position, sun: Position) -> bool:
    if planet.name not in COMBUSTION_ORB:
        return False
    orb = COMBUSTION_ORB_RETRO.get(planet.name, COMBUSTION_ORB[planet.name]) if planet.retrograde else COMBUSTION_ORB[planet.name]
    return _sep(planet.longitude, sun.longitude) <= orb


def dignity(planet: str, sign: str) -> str | None:
    """domicile / exaltation / detriment / fall for the seven classical planets."""
    if planet not in EXALTATION:
        return None
    ruled = {s for s, r in TRADITIONAL_RULERS.items() if r == planet}
    if sign in ruled:
        return "domicile"
    if sign == EXALTATION[planet]:
        return "exaltation"
    if sign in {_opposite(s) for s in ruled}:
        return "detriment"
    if sign == _opposite(EXALTATION[planet]):
        return "fall"
    return None


def _sep(a: float, b: float) -> float:
    d = abs(_norm360(a - b))
    return min(d, 360 - d)


@dataclass
class Pattern:
    kind: str            # "stellium", "grand trine", "t-square", "grand cross"
    planets: list[str]
    detail: str


@dataclass
class DashaPeriod:
    lord: str
    start: str           # ISO date
    end: str
    sub_periods: list["DashaPeriod"] = field(default_factory=list)


@dataclass
class Yoga:
    name: str
    planets: list[str]
    meaning_key: str     # short tag the reading layer can expand
    strength: str = "full"   # full / partial / cancelled
    note: str = ""           # why it is partial or cancelled, in plain words


@dataclass
class ChartInsights:
    system: str
    elements: dict[str, float]
    modalities: dict[str, float]
    dominant_element: str
    dominant_modality: str
    dignities: dict[str, str]
    retrogrades: list[str]
    patterns: list[Pattern]
    house_rulers: list[dict] | None       # [{house, sign, ruler, ruler_house, ruler_sign}]
    sect: str | None                      # "day" or "night" chart (needs birth time)
    part_of_fortune: dict | None
    birth_moon_phase: str
    # Vedic only
    current_dasha: dict | None = None
    dashas: list[DashaPeriod] | None = None
    navamsa: dict[str, str] | None = None
    yogas: list[Yoga] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- Western-style facts
def balance(chart: BirthChart) -> tuple[dict[str, float], dict[str, float]]:
    elements = {e: 0.0 for e in ("fire", "earth", "air", "water")}
    modalities = {m: 0.0 for m in ("cardinal", "fixed", "mutable")}
    points: list[Position] = [p for p in chart.planets if p.name in _BALANCE_BODIES]
    if chart.ascendant:
        points.append(chart.ascendant)
    for p in points:
        w = _BALANCE_WEIGHT.get(p.name, 1)
        elements[ELEMENT[p.sign]] += w
        modalities[MODALITY[p.sign]] += w
    return elements, modalities


def find_patterns(chart: BirthChart) -> list[Pattern]:
    bodies = [p for p in chart.planets if p.name in _BALANCE_BODIES]
    out: list[Pattern] = []

    # Stellium: 3+ planets in one sign (or, with a birth time, one house).
    by_sign: dict[str, list[str]] = {}
    for p in bodies:
        by_sign.setdefault(p.sign, []).append(p.name)
    for sign, names in by_sign.items():
        if len(names) >= 3:
            out.append(Pattern("stellium", names, f"{len(names)} planets in {sign}"))
    if chart.time_known:
        by_house: dict[int, list[str]] = {}
        for p in bodies:
            by_house.setdefault(p.house, []).append(p.name)  # type: ignore[arg-type]
        for house, names in by_house.items():
            if len(names) >= 3 and not any(set(names) == set(x.planets) for x in out):
                out.append(Pattern("stellium", names, f"{len(names)} planets in house {house}"))

    lon = {p.name: p.longitude for p in bodies}
    names = list(lon)

    def near(a: str, b: str, angle: float, orb: float) -> bool:
        return abs(_sep(lon[a], lon[b]) - angle) <= orb

    for a, b, c in combinations(names, 3):
        if near(a, b, 120, 7) and near(b, c, 120, 7) and near(a, c, 120, 7):
            out.append(Pattern("grand trine", [a, b, c], f"in {ELEMENT[_sign_of(lon[a])]} signs"))
    for a, b in combinations(names, 2):
        if not near(a, b, 180, 7):
            continue
        for c in names:
            if c in (a, b):
                continue
            if near(a, c, 90, 6) and near(b, c, 90, 6):
                out.append(Pattern("t-square", [a, b, c], f"{c} is the focal point"))
    for a, b, c, d in combinations(names, 4):
        pairs_opp = [(a, b, c, d), (a, c, b, d), (a, d, b, c)]
        for w, x, y, z in pairs_opp:
            if near(w, x, 180, 7) and near(y, z, 180, 7) and near(w, y, 90, 7) and near(x, z, 90, 7):
                out.append(Pattern("grand cross", [w, x, y, z], "four planets in a square"))
                break
    # A grand cross contains t-squares; keep only the bigger pattern.
    crosses = [set(p.planets) for p in out if p.kind == "grand cross"]
    return [p for p in out if not (p.kind == "t-square" and any(set(p.planets) <= c for c in crosses))]


def _sign_of(lon: float) -> str:
    return SIGNS[int(_norm360(lon) // 30)]


def house_rulers(chart: BirthChart) -> list[dict] | None:
    if not chart.house_cusps:
        return None
    out = []
    for i, cusp in enumerate(chart.house_cusps):
        sign = _sign_of(cusp)
        ruler = TRADITIONAL_RULERS[sign]
        rp = chart.planet(ruler)
        out.append({"house": i + 1, "sign": sign, "ruler": ruler, "ruler_house": rp.house, "ruler_sign": rp.sign})
    return out


def sect_and_fortune(chart: BirthChart) -> tuple[str | None, dict | None]:
    if not chart.ascendant or not chart.house_cusps:
        return None, None
    sun = chart.planet("Sun")
    moon = chart.planet("Moon")
    day = sun.house is not None and sun.house >= 7  # Sun above the horizon (houses 7-12)
    asc = chart.ascendant.longitude
    pof = _norm360(asc + moon.longitude - sun.longitude) if day else _norm360(asc + sun.longitude - moon.longitude)
    return ("day" if day else "night"), {
        "longitude": pof,
        "sign": _sign_of(pof),
        "degree": pof % 30,
        "house": _house_of(pof, chart.house_cusps),
    }


PHASES = ["New Moon", "Crescent", "First Quarter", "Gibbous", "Full Moon", "Disseminating", "Last Quarter", "Balsamic"]


def birth_moon_phase(chart: BirthChart) -> str:
    elong = _norm360(chart.planet("Moon").longitude - chart.planet("Sun").longitude)
    return PHASES[int(elong // 45)]


# ---------------------------------------------------------------- Vedic facts
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
YEAR_DAYS = 365.25  # see docs/decisions.md
NAKSHATRA_SPAN = 360 / 27


def vimshottari(moon_sidereal_lon: float, birth_utc: datetime, now: datetime | None = None) -> tuple[list[DashaPeriod], dict]:
    """Mahadashas from birth for 120 years, with antardashas, and the period running `now`."""
    lon = _norm360(moon_sidereal_lon)
    n = int(lon // NAKSHATRA_SPAN) % 27
    first_lord = DASHA_ORDER[n % 9]
    elapsed_fraction = (lon % NAKSHATRA_SPAN) / NAKSHATRA_SPAN
    start_index = DASHA_ORDER.index(first_lord)

    # The first dasha started before birth: back-date it by the elapsed part.
    t = birth_utc - timedelta(days=elapsed_fraction * DASHA_YEARS[first_lord] * YEAR_DAYS)
    periods: list[DashaPeriod] = []
    for k in range(9):
        lord = DASHA_ORDER[(start_index + k) % 9]
        length = timedelta(days=DASHA_YEARS[lord] * YEAR_DAYS)
        subs: list[DashaPeriod] = []
        st = t
        for j in range(9):
            sub_lord = DASHA_ORDER[(DASHA_ORDER.index(lord) + j) % 9]
            sub_len = length * (DASHA_YEARS[sub_lord] / 120)
            subs.append(DashaPeriod(sub_lord, st.date().isoformat(), (st + sub_len).date().isoformat()))
            st += sub_len
        periods.append(DashaPeriod(lord, t.date().isoformat(), (t + length).date().isoformat(), subs))
        t += length

    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    current: dict = {}
    for p in periods:
        if p.start <= today < p.end:
            current = {"mahadasha": p.lord, "mahadasha_start": p.start, "mahadasha_end": p.end}
            for s in p.sub_periods:
                if s.start <= today < s.end:
                    current.update({"antardasha": s.lord, "antardasha_start": s.start, "antardasha_end": s.end})
            break
    current["birth_balance_years"] = round((1 - elapsed_fraction) * DASHA_YEARS[first_lord], 2)
    current["birth_dasha"] = first_lord
    return periods, current


def navamsa_sign(lon: float) -> str:
    """D9 sign: each sign is cut into nine 3°20' parts, counted on continuously from Aries."""
    return SIGNS[int(_norm360(lon) * 9 / 30 + 1e-9) % 12]


def _house_from(sign_from: str, sign_to: str) -> int:
    return (SIGNS.index(sign_to) - SIGNS.index(sign_from)) % 12 + 1


def find_yogas(chart: BirthChart) -> list[Yoga]:
    p = {x.name: x for x in chart.planets}
    out: list[Yoga] = []
    moon = p["Moon"].sign
    jup = p["Jupiter"]
    if _house_from(moon, jup.sign) in (1, 4, 7, 10):
        # Classical condition: Jupiter must not be debilitated, combust or in an enemy's sign.
        problems = []
        if (vedic_dignity("Jupiter", jup.longitude) or "").endswith("debilitation"):
            problems.append("Jupiter is debilitated")
        if is_combust(jup, p["Sun"]):
            problems.append("Jupiter is combust")
        if TRADITIONAL_RULERS[jup.sign] in NATURAL_ENEMIES["Jupiter"]:
            problems.append(f"Jupiter is in the sign of its enemy {TRADITIONAL_RULERS[jup.sign]}")
        if not problems:
            out.append(Yoga("Gajakesari", ["Jupiter", "Moon"], "wisdom-reputation"))
    if p["Sun"].sign == p["Mercury"].sign:
        out.append(Yoga("Budhaditya", ["Sun", "Mercury"], "intellect"))
    if p["Moon"].sign == p["Mars"].sign:
        out.append(Yoga("Chandra-Mangala", ["Moon", "Mars"], "drive-resources"))
    elif _house_from(moon, p["Mars"].sign) == 7:
        out.append(Yoga("Chandra-Mangala", ["Moon", "Mars"], "drive-resources", "partial",
                        "Moon and Mars face each other rather than sharing a sign, a milder form"))
    if chart.ascendant:
        lagna = chart.ascendant.sign
        names = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya", "Saturn": "Sasa"}
        for planet, yoga in names.items():
            d = vedic_dignity(planet, p[planet].longitude)
            if d in ("own sign", "moolatrikona", "exaltation", "deep exaltation") and _house_from(lagna, p[planet].sign) in (1, 4, 7, 10):
                out.append(Yoga(f"{yoga} (Pancha Mahapurusha)", [planet], f"mahapurusha-{planet.lower()}"))
    # Kemadruma: no planet (other than Sun and the nodes) in the 2nd or 12th from the Moon.
    neighbours = [x for x in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
                  if _house_from(moon, p[x].sign) in (2, 12)]
    if not neighbours:
        # Standard cancellations (Rao, Behari): a planet in an angle from the Ascendant
        # or from the Moon, or the Moon itself in an angle from the Ascendant.
        others = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
        reasons = []
        if any(_house_from(moon, p[x].sign) in (1, 4, 7, 10) for x in others):
            reasons.append("a planet sits in an angle from the Moon")
        if chart.ascendant:
            lagna = chart.ascendant.sign
            if any(_house_from(lagna, p[x].sign) in (1, 4, 7, 10) for x in others):
                reasons.append("a planet sits in an angle from the Ascendant")
            if _house_from(lagna, moon) in (1, 4, 7, 10):
                reasons.append("the Moon sits in an angle from the Ascendant")
        if reasons:
            out.append(Yoga("Kemadruma", ["Moon"], "self-reliance", "cancelled", (lambda t: t[0].upper() + t[1:])("; ".join(reasons))))
        else:
            out.append(Yoga("Kemadruma", ["Moon"], "self-reliance"))
    return out


# ---------------------------------------------------------------- entry point
def chart_insights(chart: BirthChart, now: datetime | None = None) -> ChartInsights:
    elements, modalities = balance(chart)
    if chart.system == "vedic":
        dignities = {p.name: d for p in chart.planets if (d := vedic_dignity(p.name, p.longitude))}
    else:
        dignities = {p.name: d for p in chart.planets if (d := dignity(p.name, p.sign))}
    retro = [p.name for p in chart.planets
             if p.retrograde and p.name not in ("North Node", "South Node", "Rahu", "Ketu")]
    sect, fortune = sect_and_fortune(chart)
    insights = ChartInsights(
        system=chart.system,
        elements=elements,
        modalities=modalities,
        dominant_element=max(elements, key=lambda k: elements[k]),
        dominant_modality=max(modalities, key=lambda k: modalities[k]),
        dignities=dignities,
        retrogrades=retro,
        patterns=find_patterns(chart),
        house_rulers=house_rulers(chart),
        sect=sect,
        part_of_fortune=fortune,
        birth_moon_phase=birth_moon_phase(chart),
    )
    if chart.system == "vedic":
        birth = datetime.fromisoformat(chart.utc_time)
        insights.dashas, insights.current_dasha = vimshottari(chart.planet("Moon").longitude, birth, now)
        insights.navamsa = {x.name: navamsa_sign(x.longitude) for x in chart.planets}
        if chart.ascendant:
            insights.navamsa["Lagna"] = navamsa_sign(chart.ascendant.longitude)
        insights.yogas = find_yogas(chart)
    return insights
