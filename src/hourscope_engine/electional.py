"""Power Day Finder: the best windows for an activity over a date range.

Classic electional astrology, kept simple and transparent. For each waking
planetary hour in the range we start from the person's own hour score
(daily.py) and add activity rules:

- the hour's planet suits the activity (primary or supporting planet)
- the Moon is waxing for things you want to grow (launch, start, ask)
- the Moon is not void of course (Western)
- the activity's key planet is not retrograde (e.g. Mercury for signing)
- the Moon makes a helpful aspect to the activity's key planet, or a hard one to Saturn/Mars
- the day's overall rating

Every window comes with its reasons, and every number comes from code (rule 1).

Upgrade (2026-11-14, docs/research/western-depth-and-timing.md 3.15 and
vedic-timing.md muhurta): each rule is recorded as a check (passed / failed,
with points) so the page can show "why this window". The top candidates are
then refined with a chart cast for the moment at the user's location:
- Western: the rising sign's ruler not retrograde or combust, the activity's
  house ruler angular or succedent, the rising sign's mode (movable for travel,
  fixed for lasting things), and fit with the natal chart (the Moon trine or
  sextile natal Venus/Jupiter, or square/conjunct natal Saturn/Mars).
- Vedic: rikta tithis and Amavasya, Vishti karana and avoided nitya yogas at
  that moment, a supportive nakshatra, the person's tara and chandra bala, the
  hour planet's houses in the natal chart for the activity (hora by house),
  and the natal Ashtakavarga of the rising, Moon and Sun signs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

from .chart import NAKSHATRAS, SIGNS, BirthChart, chart_at_utc
from .daily import aspect_between, daily_report
from .insights import TRADITIONAL_RULERS
from .panchanga import AVOIDED_YOGAS, NITYA_YOGAS, karana_index, karana_name, nakshatra_index, yoga_index
from .sky import jd_from_datetime, longitude_of

RULES_VERSION = "2026-11-14.2"
REFINE_TOP = 40           # candidates refined with a chart for the moment
# The life areas (houses) each activity belongs to; the first is the main one.
ACTIVITY_HOUSES = {"launch": (10, 1), "sign": (7, 3), "ask": (11, 10), "travel": (3, 9, 12), "start": (1, 10),
                   "love": (5, 7), "money": (2, 11), "create": (5,), "focus": (4, 5)}
LASTING = {"sign", "money", "start", "launch"}      # want a fixed rising sign
GOOD_STARS = {"Ashwini", "Rohini", "Mrigashira", "Punarvasu", "Pushya", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
              "Anuradha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Uttara Bhadrapada", "Revati"}
MOVABLE = {"Aries", "Cancer", "Libra", "Capricorn"}
FIXED = {"Taurus", "Leo", "Scorpio", "Aquarius"}
MAX_DAYS = 62


@dataclass(frozen=True)
class Activity:
    id: str
    label: str
    primary: tuple[str, ...]        # hour planets that suit it best
    supporting: tuple[str, ...]     # also good
    key_planet: str                 # the planet whose condition matters most
    wants_waxing: bool              # things you want to grow
    avoid_retrograde: tuple[str, ...]


ACTIVITIES: dict[str, Activity] = {a.id: a for a in [
    Activity("launch", "Launch something", ("Sun", "Jupiter"), ("Mars", "Mercury"), "Sun", True, ("Mercury",)),
    Activity("sign", "Sign a contract or agreement", ("Mercury", "Jupiter"), ("Venus",), "Mercury", True, ("Mercury",)),
    Activity("ask", "Ask for something (a favour, a raise, a yes)", ("Jupiter", "Venus"), ("Sun",), "Jupiter", True, ()),
    Activity("travel", "Travel or set off", ("Mercury", "Moon"), ("Jupiter",), "Mercury", False, ("Mercury",)),
    Activity("start", "Start a new habit or project", ("Mars", "Sun"), ("Jupiter", "Saturn"), "Mars", True, ("Mars",)),
    Activity("love", "A date or important conversation with someone you love", ("Venus", "Moon"), ("Jupiter",), "Venus", True, ("Venus",)),
    Activity("money", "Money matters (planning, buying, pricing)", ("Jupiter", "Venus"), ("Saturn", "Mercury"), "Jupiter", True, ("Mercury", "Venus")),
    Activity("create", "Creative work", ("Venus", "Sun"), ("Moon", "Mercury"), "Venus", False, ()),
    Activity("focus", "Deep work, study or planning", ("Saturn", "Mercury"), ("Sun",), "Saturn", False, ()),
]}

RULES = {
    "personal_weight": 0.6,       # how much the person's own hour score counts (the rest is the activity's rules)
    "primary": 16,
    "supporting": 6,
    "wrong_planet": -6,           # the hour's planet works against it (Saturn for a date, Mars for signing)
    "waxing": 6,
    "waning_penalty": -4,
    "void": -18,
    "retrograde": -20,
    "moon_helps_key": 8,          # Moon trine/sextile/conjunct the key planet
    "moon_hard_malefic": -6,      # Moon square/opposite Saturn or Mars
    "day_rating": 1.5,            # per rating point above/below 5.5
    "moon_aspect_orb": 6.0,
    # Refinement (chart for the moment)
    "asc_ruler_ok": 4, "asc_ruler_weak": -4,
    "matter_ruler_strong": 4,
    "rising_mode": 3,
    "natal_benefic": 4, "natal_malefic": -4,
    # Vedic muhurta
    "rikta": -6, "vishti": -8, "avoided_yoga": -5, "good_star": 4,
    "tara_good": 4, "tara_bad": -5, "chandra_good": 3, "chandra_rest": -6,
    "hora_house_good": 5, "hora_house_bad": -5,
    "sav_good": 3, "sav_weak": -3,
}

# Hour planets that work against each activity.
AGAINST = {
    "love": ("Saturn", "Mars"), "sign": ("Mars",), "ask": ("Saturn",), "travel": ("Saturn",),
    "money": ("Mars",), "create": ("Saturn",), "launch": ("Saturn",), "start": (), "focus": ("Venus",),
}


@dataclass
class Window:
    date: str
    start: str
    end: str
    ruler: str
    score: int
    day_rating: int
    reasons: list[str]
    checks: list[dict]          # {label, ok, points}: the "why this window" list

    def to_dict(self) -> dict:
        return asdict(self)


def _elongation(jd: float) -> float:
    return (longitude_of("Moon", jd)[0] - longitude_of("Sun", jd)[0]) % 360


def find_power_windows(
    chart: BirthChart,
    birth_date: date,
    activity_id: str,
    start: date,
    days: int,
    latitude: float,
    longitude: float,
    timezone_name: str | None = None,
    top: int = 10,
) -> list[Window]:
    if activity_id not in ACTIVITIES:
        raise ValueError(f"unknown activity '{activity_id}'")
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_DAYS}")
    act = ACTIVITIES[activity_id]
    sidereal = chart.system == "vedic"
    r = RULES
    windows: list[Window] = []

    for k in range(days):
        d = start + timedelta(days=k)
        rep = daily_report(chart, birth_date, d, latitude, longitude, timezone_name)
        void = None
        if rep.moon.get("void_start") and rep.moon.get("void_end"):
            void = (datetime.fromisoformat(rep.moon["void_start"]), datetime.fromisoformat(rep.moon["void_end"]))
        retro = {p["planet"] for p in rep.sky if p["retrograde"]}

        for h in rep.hours:
            s_dt, e_dt = datetime.fromisoformat(h.start), datetime.fromisoformat(h.end)
            mid = s_dt + (e_dt - s_dt) / 2
            # Waking hours only (07:00-22:00 local), and only on this calendar date.
            if mid.date() != d or not (7 <= mid.hour < 22):
                continue
            base = r["personal_weight"] * h.score + (1 - r["personal_weight"]) * 50
            reasons = [f"{h.ruler} hour: your personal score {h.score}"]
            checks: list[dict] = []

            def check(label: str, ok: bool, points: float, _checks: list[dict] = checks) -> float:
                _checks.append({"label": label, "ok": ok, "points": round(points)})
                return points

            score = base

            if h.ruler in act.primary:
                score += check(f"{h.ruler} is a leading planet for this", True, r["primary"])
            elif h.ruler in act.supporting:
                score += check(f"{h.ruler} supports this", True, r["supporting"])
            elif h.ruler in AGAINST.get(act.id, ()):
                score += check(f"{h.ruler} works against this", False, r["wrong_planet"])

            jd = jd_from_datetime(mid)
            elong = _elongation(jd)
            if act.wants_waxing:
                if elong < 180:
                    score += check("The Moon is waxing (growing)", True, r["waxing"])
                else:
                    score += check("The Moon is waning", False, r["waning_penalty"])

            if void and void[0] <= mid < void[1] and not sidereal:
                score += check("The Moon is void of course", False, r["void"])

            for p in act.avoid_retrograde:
                if p in retro:
                    score += check(f"{p} is retrograde", False, r["retrograde"])

            moon_lon = longitude_of("Moon", jd, sidereal)[0]
            key_lon = longitude_of(act.key_planet, jd, sidereal)[0] if act.key_planet != "Moon" else None
            if key_lon is not None:
                hit = aspect_between(moon_lon, key_lon, r["moon_aspect_orb"])
                if hit and hit[0] in ("trine", "sextile", "conjunction"):
                    score += check(f"The Moon {hit[0]} {act.key_planet} in the sky", True, r["moon_helps_key"])
            for malefic in ("Saturn", "Mars"):
                if malefic == act.key_planet:
                    continue
                hit = aspect_between(moon_lon, longitude_of(malefic, jd, sidereal)[0], r["moon_aspect_orb"])
                if hit and hit[0] in ("square", "opposition"):
                    score += check(f"The Moon {hit[0]} {malefic} in the sky", False, r["moon_hard_malefic"])
                    break

            score += check(f"The day rates {rep.rating}/10 for you", rep.rating >= 6, r["day_rating"] * (rep.rating - 5.5))

            # Vedic muhurta: panchanga at this moment and the person's own stars.
            if sidereal and rep.panchanga:
                pc = rep.panchanga
                if pc["tithi"].get("note"):
                    score += check(f"{pc['tithi']['name']} is a pause day in the lunar month", False, r["rikta"])
                if karana_name(karana_index(jd)) == "Vishti":
                    score += check("Vishti karana: a pause, less ideal for starts", False, r["vishti"])
                yoga = NITYA_YOGAS[yoga_index(jd)]
                if yoga in AVOIDED_YOGAS:
                    score += check(f"{yoga} yoga is less ideal for new starts", False, r["avoided_yoga"])
                star = NAKSHATRAS[nakshatra_index(jd)]
                if star in GOOD_STARS:
                    score += check(f"The Moon is in {star}, a supportive star for beginnings", True, r["good_star"])
                me = pc.get("personal")
                if me:
                    q = me["tara"]["quality"]
                    if q == "good":
                        score += check(f"Your {me['tara']['name']} tara: supportive", True, r["tara_good"])
                    elif q in ("challenging", "rest"):
                        score += check(f"Your {me['tara']['name']} tara: go gently", False, r["tara_bad"])
                    cb = me["chandra_bala"]
                    if cb["quality"] == "good":
                        score += check(f"The Moon is {_ord(cb['house'])} from your Moon: supportive", True, r["chandra_good"])
                    elif cb["quality"] == "rest":
                        score += check("The Moon is 8th from your Moon: a rest day", False, r["chandra_rest"])

            windows.append(Window(
                date=d.isoformat(), start=h.start, end=h.end, ruler=h.ruler,
                score=max(0, min(100, round(score))), day_rating=rep.rating,
                reasons=reasons + [c["label"] for c in checks], checks=checks,
            ))

    windows.sort(key=lambda w: (-w.score, w.start))
    for w in windows[:REFINE_TOP]:
        _refine(w, chart, act, latitude, longitude, timezone_name)
    windows.sort(key=lambda w: (-w.score, w.start))
    # Keep the list varied: at most two windows from the same day.
    picked: list[Window] = []
    per_day: dict[str, int] = {}
    for w in windows:
        if per_day.get(w.date, 0) >= 2:
            continue
        picked.append(w)
        per_day[w.date] = per_day.get(w.date, 0) + 1
        if len(picked) >= top:
            break
    return picked


def _ord(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _refine(w: Window, chart: BirthChart, act: Activity, latitude: float, longitude: float, timezone_name: str | None) -> None:
    """Add the checks that need a chart for the moment (rising sign, rulers) and the natal chart."""
    r = RULES
    sidereal = chart.system == "vedic"
    s_dt, e_dt = datetime.fromisoformat(w.start), datetime.fromisoformat(w.end)
    mid = s_dt + (e_dt - s_dt) / 2
    try:
        m = chart_at_utc(mid, latitude, longitude, chart.system)
    except ValueError:
        return
    if m.ascendant is None:
        return
    delta = 0.0

    def add(label: str, ok: bool, points: float) -> None:
        nonlocal delta
        delta += points
        w.checks.append({"label": label, "ok": ok, "points": round(points)})
        w.reasons.append(label)

    p = {x.name: x for x in m.planets}
    rising = m.ascendant.sign
    ruler = TRADITIONAL_RULERS[rising]
    rp, sun = p[ruler], p["Sun"]
    combust = ruler != "Sun" and abs(((rp.longitude - sun.longitude + 180) % 360) - 180) <= 8.5
    if rp.retrograde or combust:
        add(f"{rising} rising: its ruler {ruler} is {'retrograde' if rp.retrograde else 'too close to the Sun'}", False, r["asc_ruler_weak"])
    else:
        add(f"{rising} rising: its ruler {ruler} is free to act", True, r["asc_ruler_ok"])
    house = ACTIVITY_HOUSES[act.id][0]
    if sidereal:
        cusp_sign = SIGNS[(SIGNS.index(rising) + house - 1) % 12]
    elif m.house_cusps:
        cusp_sign = SIGNS[int(m.house_cusps[house - 1] // 30)]
    else:
        cusp_sign = None
    if cusp_sign:
        lord = p[TRADITIONAL_RULERS[cusp_sign]]
        if lord.house and (lord.house - 1) % 3 in (0, 1):
            add(f"{lord.name}, ruler of the {_ord(house)} house for this, is well placed", True, r["matter_ruler_strong"])
    if act.id == "travel" and rising in MOVABLE:
        add(f"{rising} rising, a moving sign, suits travel", True, r["rising_mode"])
    if act.id in LASTING and rising in FIXED:
        add(f"{rising} rising, a fixed sign, suits something meant to last", True, r["rising_mode"])

    # Fit with the natal chart.
    moon = p["Moon"].longitude
    natal = {x.name: x for x in chart.planets}
    for benefic in ("Venus", "Jupiter"):
        hit = aspect_between(moon, natal[benefic].longitude, 4.0)
        if hit and hit[0] in ("trine", "sextile"):
            add(f"The Moon {hit[0]} your natal {benefic}", True, r["natal_benefic"])
            break
    for malefic in ("Saturn", "Mars"):
        hit = aspect_between(moon, natal[malefic].longitude, 4.0)
        if hit and hit[0] in ("conjunction", "square"):
            add(f"The Moon {hit[0]} your natal {malefic}", False, r["natal_malefic"])
            break

    if sidereal and chart.time_known and chart.ascendant is not None:
        # Hora by natal house: is the hour's planet tied to this activity's houses (or trines from them)?
        lagna = SIGNS.index(chart.ascendant.sign)
        ruled = {(SIGNS.index(sg) - lagna) % 12 + 1 for sg, lord in TRADITIONAL_RULERS.items() if lord == w.ruler}
        sits = natal[w.ruler].house
        targets: set[int] = set()
        bad: set[int] = set()
        for h0 in ACTIVITY_HOUSES[act.id]:
            targets |= {h0, (h0 + 3) % 12 + 1, (h0 + 7) % 12 + 1}           # the house and its trines
            bad |= {(h0 + 4) % 12 + 1, (h0 + 6) % 12 + 1, (h0 + 10) % 12 + 1}  # 6th, 8th, 12th from it
        if (ruled | {sits}) & targets:
            add(f"In your chart {w.ruler} is tied to the houses this activity needs", True, r["hora_house_good"])
        elif ruled & bad:
            add(f"In your chart {w.ruler} rules a house that works against this", False, r["hora_house_bad"])
        # The natal Ashtakavarga of the moment's rising, Moon and Sun signs.
        from .vedic_seasons import SEVEN, ashtakavarga
        signs = {n: int(natal[n].longitude // 30) for n in SEVEN}
        signs["Ascendant"] = lagna
        sav = ashtakavarga(signs)["sav"]
        for label, sign in (("rising sign", rising), ("Moon", p["Moon"].sign), ("Sun", sun.sign)):
            pts = sav[SIGNS.index(sign)]
            if pts >= 30:
                add(f"The {label} falls in one of your strong signs ({pts} points)", True, r["sav_good"])
            elif pts < 25:
                add(f"The {label} falls in one of your weaker signs ({pts} points)", False, r["sav_weak"])
    w.score = max(0, min(100, round(w.score + delta)))

