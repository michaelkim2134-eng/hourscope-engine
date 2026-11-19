"""Today's energy (theme + rating) and the user's best hours.

Every number here comes from the rules below, never from the AI (ground
rule 1). The rules and weights are collected in SCORING so they can be
tuned in one place; docs/scoring.md explains them in plain English.

Inputs: the user's natal chart (Western or Vedic), their birth date (for
numerology), their CURRENT location, and the local date.
"""

from __future__ import annotations

import math
import re

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import swisseph as swe

from .chart import SIGNS, BirthChart
from .profections import profection
from .panchanga import day_windows, panchanga
from .hours import PlanetaryDay, planetary_day
from .lunar import MoonState, moon_state, void_of_course_window
from .numerology import NUMBER_THEMES, Numerology, planet_for
from .places import timezone_at
from .sky import angle_diff, datetime_from_jd, jd_from_datetime, longitude_of

SCORING_VERSION = "2026-11-13.4"

SCORING = {
    "hour_base": 50,
    # The hour ruler's sign in the sky right now
    "domicile": 10, "exaltation": 8, "detriment": -8, "fall": -10,
    "retrograde": -8,
    # How the hour ruler relates to this user
    "chart_ruler": 10,          # ruler of the Ascendant sign (Sun sign if birth time unknown)
    "sun_sign_ruler": 6,
    "life_path_planet": 6,
    "personal_day_planet": 4,
    # The hour ruler's aspects to the user's natal Sun, Moon, Ascendant and itself
    "hour_aspect_orb": 3.0,
    "hour_aspect_good": 6,      # trine, sextile; conjunction of a benefic
    "hour_aspect_bad": -6,      # square, opposition; conjunction of a malefic
    "hour_aspect_neutral_conj": 3,
    "hour_aspect_cap": 18,
    # Changes hour by hour
    "angular": 6,               # hour ruler rising or at its highest at the user's location
    "angular_orb": 8.0,
    "moon_aspect_orb": 3.0,     # the Moon to natal Sun, Moon, Ascendant, Venus, Jupiter
    "moon_aspect_good": 5,
    "moon_aspect_bad": -5,
    "moon_aspect_conj": 3,
    "moon_aspect_cap": 10,
    # Timing cautions
    "void_of_course_moon": -12,  # Western
    "rahu_kaal": -15,            # Vedic
    "yamaganda": -10,            # Vedic (scaled by overlap, like Rahu Kaal)
    "gulika": -6,                # Vedic
    "abhijit": 8,                # Vedic: the midday muhurta (not on Wednesdays)
    # Best-hours selection
    "waking_start": time(7, 0),
    "waking_end": time(22, 0),
    "best_count": 3,
    "caution_below": 40,
    # Daily rating (1-10)
    "rating_center": 5.4,
    "rating_spread": 1.2,               # soft curve: spreads the middle, keeps 1s and 10s rare
    "rating_orbs": {"Moon": 5.0, "Sun": 3.0, "Mercury": 3.0, "Venus": 3.0, "Mars": 3.0,
                    "Jupiter": 2.0, "Saturn": 2.0},
    "rating_weights": {"Moon": 1.0, "Sun": 1.5, "Mercury": 1.0, "Venus": 1.5, "Mars": 1.5,
                       "Jupiter": 2.0, "Saturn": 2.0},
    "rating_void_penalty": -1.0,  # Western: Moon void for over half the waking day
    # The Moon drives day-to-day variety (added 2026-11-13; see docs/scoring.md)
    "rating_moon_element": {"same": 0.8, "compatible": 0.4, "other": -0.5},
    "rating_moon_extra_orb": 5.0,       # Moon to natal Venus, Jupiter, Mars, Saturn
    "rating_moon_extra_weight": 0.9,
    "rating_best_hour_weight": 1.0,     # how strong today's best waking hour is
    "rating_best_hour_center": 64,      # a typical best hour; above lifts the day, below lowers it
    "rating_rahu_penalty": 0.0,
    # Vedic personal stars (today's Moon from the natal Moon)
    "rating_tara": {"good": 0.4, "mixed": 0.0, "challenging": -0.4, "rest": -0.6},
    "rating_year_lord": 1.15,           # transits by or to the lord of the year (profections) count more
    "rating_chandra_bala": {"good": 0.5, "weak": -0.4, "rest": -0.8},
}

TRADITIONAL_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}
EXALTATION = {"Sun": "Aries", "Moon": "Taurus", "Mercury": "Virgo", "Venus": "Pisces",
              "Mars": "Capricorn", "Jupiter": "Cancer", "Saturn": "Libra"}
BENEFICS = {"Venus", "Jupiter"}
MALEFICS = {"Mars", "Saturn"}

GOOD_FOR = {
    "Sun": ["career", "being seen", "leadership", "vitality"],
    "Moon": ["home and family", "self-care", "intuition", "nurturing"],
    "Mercury": ["calls and emails", "writing", "study", "contracts", "short trips"],
    "Venus": ["love and dates", "socializing", "beauty and art", "shopping"],
    "Mars": ["exercise", "competition", "bold moves", "tough tasks"],
    "Jupiter": ["money and growth", "asking for favors", "legal matters", "teaching and learning"],
    "Saturn": ["planning", "deep work", "discipline", "long-term commitments"],
}

ASPECT_KINDS = [("conjunction", 0.0), ("sextile", 60.0), ("square", 90.0),
                ("trine", 120.0), ("opposition", 180.0)]


@dataclass
class HourScore:
    number: int
    ruler: str
    start: str
    end: str
    is_day: bool
    score: int
    good_for: list[str]
    reasons: list[str]


@dataclass
class DailyReport:
    date: str
    system: str
    timezone: str
    location: tuple[float, float]
    scoring_version: str
    sunrise: str
    sunset: str
    day_ruler: str
    rating: int
    theme: dict
    numerology: dict
    moon: dict
    rahu_kaal: tuple[str, str] | None
    panchanga: dict | None
    best_hours: list[HourScore]
    caution_hours: list[HourScore]
    hours: list[HourScore]
    sky: list[dict] = field(default_factory=list)  # where the planets are today (local noon)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- helpers
def dignity(planet: str, sign: str) -> str | None:
    if planet not in EXALTATION:
        return None
    ruled = {s for s, r in TRADITIONAL_RULERS.items() if r == planet}
    if sign in ruled:
        return "domicile"
    if sign == EXALTATION[planet]:
        return "exaltation"
    opposite = lambda s: SIGNS[(SIGNS.index(s) + 6) % 12]  # noqa: E731
    if sign in {opposite(s) for s in ruled}:
        return "detriment"
    if sign == opposite(EXALTATION[planet]):
        return "fall"
    return None


def aspect_between(a: float, b: float, orb: float) -> tuple[str, float] | None:
    sep = angle_diff(a, b)
    for kind, angle in ASPECT_KINDS:
        if abs(sep - angle) <= orb:
            return kind, abs(sep - angle)
    return None


def aspect_value(kind: str, planet: str) -> int:
    s = SCORING
    if kind in ("trine", "sextile"):
        return s["hour_aspect_good"]
    if kind in ("square", "opposition"):
        return s["hour_aspect_bad"]
    if planet in BENEFICS:
        return s["hour_aspect_good"]
    if planet in MALEFICS:
        return s["hour_aspect_bad"]
    return s["hour_aspect_neutral_conj"]


def natal_points(chart: BirthChart) -> dict[str, float]:
    pts = {"Sun": chart.planet("Sun").longitude, "Moon": chart.planet("Moon").longitude}
    if chart.ascendant is not None:
        pts["Ascendant"] = chart.ascendant.longitude
    return pts


def chart_ruler(chart: BirthChart) -> str:
    sign = chart.ascendant.sign if chart.ascendant is not None else chart.planet("Sun").sign
    return TRADITIONAL_RULERS[sign]


# ---------------------------------------------------------------- hours
def score_hour(
    ruler: str, jd: float, chart: BirthChart, numbers: Numerology,
    voc: tuple[float, float] | None, rahu_fraction: float = 0.0,
    latitude: float | None = None, longitude: float | None = None,
) -> tuple[int, list[str]]:
    s = SCORING
    sidereal = chart.system == "vedic"
    score = s["hour_base"]
    reasons: list[str] = []

    lon, speed = longitude_of(ruler, jd, sidereal)
    sign = SIGNS[int(lon // 30)]
    dig = dignity(ruler, sign)
    if dig:
        score += s[dig]
        reasons.append(f"{ruler} is in {sign} ({dig})")
    if speed < 0 and ruler not in ("Sun", "Moon"):
        score += s["retrograde"]
        reasons.append(f"{ruler} is retrograde")

    c_ruler = chart_ruler(chart)
    sun_ruler = TRADITIONAL_RULERS[chart.planet("Sun").sign]
    if ruler == c_ruler:
        score += s["chart_ruler"]
        reasons.append(f"{ruler} rules your chart")
    elif ruler == sun_ruler:
        score += s["sun_sign_ruler"]
        reasons.append(f"{ruler} rules your Sun sign")
    if ruler == planet_for(numbers.life_path):
        score += s["life_path_planet"]
        reasons.append(f"{ruler} matches your Life Path {numbers.life_path}")
    if ruler == planet_for(numbers.personal_day):
        score += s["personal_day_planet"]
        reasons.append(f"{ruler} matches your Personal Day {numbers.personal_day}")

    targets = natal_points(chart)
    targets[f"natal {ruler}"] = chart.planet(ruler).longitude
    aspect_total = 0
    for name, natal_lon in targets.items():
        hit = aspect_between(lon, natal_lon, s["hour_aspect_orb"])
        if hit:
            kind, _ = hit
            if name == f"natal {ruler}" and kind == "conjunction":
                value = s["hour_aspect_good"]  # a planet returning to its own place
            else:
                value = aspect_value(kind, ruler)
            aspect_total += value
            label = name if name.startswith("natal") else f"your natal {name}"
            reasons.append(f"{ruler} {kind} {label}")
    cap = s["hour_aspect_cap"]
    score += max(-cap, min(cap, aspect_total))

    # Factors that change hour by hour.
    # 1. The hour ruler rising or culminating at the user's location right now.
    if latitude is not None and longitude is not None:
        hflags = swe.FLG_SIDEREAL if sidereal else 0
        try:
            _, ascmc = swe.houses_ex(jd, latitude, longitude, b"P", hflags)
        except swe.Error:
            _, ascmc = swe.houses_ex(jd, latitude, longitude, b"O", hflags)
        if angle_diff(lon, ascmc[0]) <= s["angular_orb"]:
            score += s["angular"]
            reasons.append(f"{ruler} is rising where you are")
        elif angle_diff(lon, ascmc[1]) <= s["angular_orb"]:
            score += s["angular"]
            reasons.append(f"{ruler} is at its highest point where you are")

    # 2. The Moon (the fastest timer) aspecting the user's chart.
    moon_lon = longitude_of("Moon", jd, sidereal)[0]
    moon_targets = natal_points(chart)
    moon_targets.update({"Venus": chart.planet("Venus").longitude, "Jupiter": chart.planet("Jupiter").longitude})
    moon_total = 0
    for name, natal_lon in moon_targets.items():
        hit = aspect_between(moon_lon, natal_lon, s["moon_aspect_orb"])
        if not hit:
            continue
        kind, _ = hit
        if kind in ("trine", "sextile"):
            value = s["moon_aspect_good"]
        elif kind in ("square", "opposition"):
            value = s["moon_aspect_bad"]
        else:
            value = s["moon_aspect_good"] if name in ("Venus", "Jupiter") else s["moon_aspect_conj"]
        moon_total += value
        reasons.append(f"the Moon {kind} your natal {name}")
    mcap = s["moon_aspect_cap"]
    score += max(-mcap, min(mcap, moon_total))

    if voc and voc[0] <= jd < voc[1]:
        score += s["void_of_course_moon"]
        reasons.append("the Moon is void of course")
    if rahu_fraction > 0:
        # Scaled by how much of the hour falls inside Rahu Kaal.
        score += s["rahu_kaal"] * rahu_fraction
        reasons.append("Rahu Kaal" if rahu_fraction >= 0.99 else f"partly in Rahu Kaal ({round(rahu_fraction * 100)}%)")

    return max(0, min(100, round(score))), reasons


# ---------------------------------------------------------------- rating
ELEMENT_OF = {s: e for s, e in zip(SIGNS, ["fire", "earth", "air", "water"] * 3)}
COMPATIBLE = {("fire", "air"), ("air", "fire"), ("earth", "water"), ("water", "earth")}


def moon_element_harmony(moon_sign_today: str, natal_moon_sign: str) -> tuple[str, float]:
    """How today's Moon sign sits with your natal Moon sign: same element, compatible, or other."""
    a, b = ELEMENT_OF[moon_sign_today], ELEMENT_OF[natal_moon_sign]
    kind = "same" if a == b else "compatible" if (a, b) in COMPATIBLE else "other"
    return kind, SCORING["rating_moon_element"][kind]


def moon_extra_transits(chart: BirthChart, jd: float) -> list[tuple[float, str]]:
    """The Moon's aspects to natal Venus and Jupiter (lift) and Mars and Saturn (friction)."""
    s = SCORING
    sidereal = chart.system == "vedic"
    moon_lon = longitude_of("Moon", jd, sidereal)[0]
    out: list[tuple[float, str]] = []
    for name in ("Venus", "Jupiter", "Mars", "Saturn"):
        hit = aspect_between(moon_lon, chart.planet(name).longitude, s["rating_moon_extra_orb"])
        if not hit:
            continue
        kind, exact = hit
        if kind in ("trine", "sextile"):
            sign = 1.0
        elif kind in ("square", "opposition"):
            sign = -1.0
        else:
            sign = 1.0 if name in BENEFICS else -1.0
        strength = 1 - exact / s["rating_moon_extra_orb"]
        out.append((sign * s["rating_moon_extra_weight"] * (0.5 + 0.5 * strength), f"transiting Moon {kind} your natal {name}"))
    return out


def daily_transits(chart: BirthChart, jd: float) -> list[tuple[float, str]]:
    """(contribution, description) for each transit to the natal Sun/Moon/Asc."""
    s = SCORING
    sidereal = chart.system == "vedic"
    out: list[tuple[float, str]] = []
    for planet, orb in s["rating_orbs"].items():
        lon = longitude_of(planet, jd, sidereal)[0]
        for name, natal_lon in natal_points(chart).items():
            hit = aspect_between(lon, natal_lon, orb)
            if not hit:
                continue
            kind, exact = hit
            if kind in ("trine", "sextile"):
                sign = 1.0
            elif kind in ("square", "opposition"):
                sign = -1.0
            else:
                sign = 1.0 if planet in BENEFICS else -1.0 if planet in MALEFICS else 0.5
            strength = 1 - exact / orb  # tighter = stronger
            value = sign * s["rating_weights"][planet] * (0.5 + 0.5 * strength)
            out.append((value, f"transiting {planet} {kind} your natal {name}"))
    return out


# ---------------------------------------------------------------- main entry
def daily_report(
    chart: BirthChart,
    birth_date: date,
    local_date: date,
    latitude: float,
    longitude: float,
    timezone_name: str | None = None,
) -> DailyReport:
    """Everything for one day at the user's current location."""
    s = SCORING
    tz = timezone_name or timezone_at(latitude, longitude)
    zone = ZoneInfo(tz)
    vedic = chart.system == "vedic"
    pd: PlanetaryDay = planetary_day(local_date, latitude, longitude, tz)
    numbers = Numerology.for_day(birth_date, local_date)
    warnings = list(pd.warnings)
    if not chart.time_known:
        warnings.append("Birth time unknown, so your Sun sign ruler stands in for your chart ruler.")

    noon_jd = jd_from_datetime(datetime.combine(local_date, time(12, 0), tzinfo=zone))
    moon: MoonState = moon_state(noon_jd, sidereal=vedic)
    voc = (moon.void_start_jd, moon.void_end_jd) if not vedic else None

    # Void periods can begin or end during the day, so look up the void
    # period for the Moon's sign at each hour (cached per sign).
    voc_cache: list[tuple[float, float, float]] = []

    def voc_for(jd: float) -> tuple[float, float] | None:
        if vedic:
            return None
        for begin, start, end in voc_cache:
            if begin <= jd < end:
                return start, end
        window = void_of_course_window(jd)
        voc_cache.append(window)
        return window[1], window[2]

    # Vedic: the full panchanga, the person's own stars, and the day windows.
    panch = panchanga(pd, chart.planet("Moon").longitude, chart.time_known) if vedic else None
    vedic_windows = {k: v for k, v in day_windows(pd).items() if k != "rahu_kaal" and v} if vedic else {}

    def window_fraction(h, w) -> float:
        return max(0.0, (min(h.end, w[1]) - max(h.start, w[0])) / (h.end - h.start))

    scored: list[HourScore] = []
    for h in pd.hours:
        jd = jd_from_datetime(h.midpoint)
        rahu_fraction = 0.0
        if vedic:
            overlap = min(h.end, pd.rahu_kaal[1]) - max(h.start, pd.rahu_kaal[0])
            rahu_fraction = max(0.0, overlap / (h.end - h.start))
        value, reasons = score_hour(h.ruler, jd, chart, numbers, voc_for(jd), rahu_fraction, latitude, longitude)
        for name, window in vedic_windows.items():
            f = window_fraction(h, window)
            if f > 0:
                label = {"yamaganda": "Yamaganda", "gulika": "Gulika", "abhijit": "Abhijit muhurta"}[name]
                value = max(0, min(100, round(value + s[name] * f)))
                reasons.append(label if f >= 0.99 else f"partly in {label} ({round(f * 100)}%)")
        scored.append(HourScore(
            number=h.number, ruler=h.ruler, start=h.start.isoformat(), end=h.end.isoformat(),
            is_day=h.is_day, score=value, good_for=GOOD_FOR[h.ruler], reasons=reasons,
        ))

    def waking(hs: HourScore) -> bool:
        mid = datetime.fromisoformat(hs.start) + (datetime.fromisoformat(hs.end) - datetime.fromisoformat(hs.start)) / 2
        local_mid = mid.astimezone(zone)
        return local_mid.date() == local_date and s["waking_start"] <= local_mid.time() < s["waking_end"]

    awake = [h for h in scored if waking(h)]
    best = sorted(awake, key=lambda h: (-h.score, h.start))[: s["best_count"]]
    best.sort(key=lambda h: h.start)
    caution = sorted([h for h in awake if h.score < s["caution_below"]], key=lambda h: h.score)[:2]
    caution.sort(key=lambda h: h.start)

    # Daily rating
    transits = daily_transits(chart, noon_jd) + moon_extra_transits(chart, noon_jd)
    # Lord of the year (profections): its transits are this year's main storyline.
    year_lord = profection(chart, datetime.combine(local_date, time(12, 0), tzinfo=zone)).lord
    # Transits TO the natal lord always count; the lord's own transits count unless it is the
    # fast Moon (whose daily aspects would otherwise boost almost every day).
    to_lord = re.compile(rf"your natal {year_lord}\b")
    by_lord = re.compile(rf"^transiting {year_lord}\b") if year_lord != "Moon" else None

    def boosted(d: str) -> bool:
        return bool(to_lord.search(d) or (by_lord and by_lord.search(d)))

    transits = [(v * s["rating_year_lord"], d + " (lord of your year)") if boosted(d) else (v, d) for v, d in transits]
    total = sum(v for v, _ in transits)
    natal_moon_sign = chart.planet("Moon").sign
    _, moon_mood = moon_element_harmony(moon.sign, natal_moon_sign)
    total += moon_mood
    if awake:
        top = max(h.score for h in awake)
        total += s["rating_best_hour_weight"] * max(-1.0, min(1.0, (top - s["rating_best_hour_center"]) / 12))
    if voc:
        wake_start = jd_from_datetime(datetime.combine(local_date, s["waking_start"], tzinfo=zone))
        wake_end = jd_from_datetime(datetime.combine(local_date, s["waking_end"], tzinfo=zone))
        void_part = max(0.0, min(wake_end, voc[1]) - max(wake_start, voc[0]))
        if void_part > (wake_end - wake_start) / 2:
            total += s["rating_void_penalty"]
    if panch and panch.personal:
        total += s["rating_tara"][panch.personal["tara"]["quality"]]
        total += s["rating_chandra_bala"][panch.personal["chandra_bala"]["quality"]]
    raw = s["rating_center"] + total
    curved = 5.5 + 4.5 * math.tanh(s["rating_spread"] * (raw - 5.5) / 4.5)
    rating = int(max(1, min(10, round(curved))))

    key = max(transits, key=lambda t: abs(t[0]))[1] if transits else None
    theme = {
        "personal_day_theme": NUMBER_THEMES[numbers.personal_day],
        "key_transit": key,
        "transits": [d for _, d in sorted(transits, key=lambda t: -abs(t[0]))],
        "day_ruler": pd.day_ruler,
        "day_ruler_good_for": GOOD_FOR[pd.day_ruler],
        "moon_sign": moon.sign,
        "moon_phase": moon.phase,
        "year_lord": year_lord,
    }
    if vedic:
        theme.update({"tithi": moon.tithi, "moon_nakshatra": moon.nakshatra})

    moon_dict = {
        "sign": moon.sign, "degree": round(moon.sign_degree, 2), "phase": moon.phase,
        "tithi": moon.tithi, "paksha": moon.paksha, "nakshatra": moon.nakshatra,
        "void_of_course_at_noon": moon.void_of_course if not vedic else None,
        "void_start": datetime_from_jd(moon.void_start_jd).astimezone(zone).isoformat() if not vedic else None,
        "void_end": datetime_from_jd(moon.void_end_jd).astimezone(zone).isoformat() if not vedic else None,
    }

    # Where the planets are today (for love/work/energy write-ups).
    sky = []
    for name in ("Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        lon, speed = longitude_of(name, noon_jd, vedic)
        sky.append({"planet": name, "sign": SIGNS[int(lon // 30)], "degree": round(lon % 30, 1),
                    "retrograde": speed < 0 and name != "Sun"})

    return DailyReport(
        date=local_date.isoformat(), system=chart.system, timezone=tz, location=(latitude, longitude),
        scoring_version=SCORING_VERSION, sunrise=pd.sunrise.isoformat(), sunset=pd.sunset.isoformat(),
        day_ruler=pd.day_ruler, rating=rating, theme=theme, numerology=asdict(numbers), moon=moon_dict,
        rahu_kaal=(pd.rahu_kaal[0].isoformat(), pd.rahu_kaal[1].isoformat()) if vedic else None,
        panchanga=panch.to_dict() if panch else None,
        best_hours=best, caution_hours=caution, hours=scored, sky=sky, warnings=warnings,
    )
