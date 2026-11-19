"""Vedic seasons: Ashtakavarga, transits from the Moon with vedha, Sade Sati and
Dhaiya, pratyantar and Yogini dashas.

See docs/research/vedic-timing.md (Ashtakavarga, gochara, Sade Sati, dashas).
- Ashtakavarga (Parashara / Brihat Jataka ch. IX): for each of the seven
  planets, a 0/1 "bindu" per sign from eight reference points (the seven
  planets and the Ascendant); totals per planet (BAV) and for all (SAV).
  Checksums enforced: Sun 48, Moon 49, Mars 39, Mercury 54, Jupiter 56,
  Venus 52, Saturn 39, SAV 337.
- Gochara: each planet's house from the natal Moon sign, favourable or not,
  and blocked by vedha (Rao tables 53-59, 63; Sun/Saturn and Moon/Mercury
  never block each other), plus its BAV bindus and the SAV of that sign.
- Sade Sati (Saturn in the 12th, 1st, 2nd from the Moon) and Dhaiya (4th, 8th),
  dated across life including retrograde re-entries.
- Pratyantar dashas inside the running antardasha; Yogini dasha (Kursija).
- Kakshya: each sign splits into eight slices of 3 deg 45 min ruled in turn by
  Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon and the Ascendant. A transit
  delivers more while it crosses a slice whose ruler gave that planet a bindu
  in the sign (Ashtakavarga), less in the others.
- Double transits (K. N. Rao's rule): a sign is "activated" while transiting
  Jupiter and Saturn both occupy or aspect it (Parashara aspects: both the 7th,
  Jupiter also the 5th and 9th, Saturn the 3rd and 10th). Reported as houses
  from the Lagna (when the birth time is known) and from the Moon.
All longitudes sidereal (Lahiri). Growth framing; no fear language.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from .chart import NAKSHATRA_SPAN, SIGNS, BirthChart
from .insights import DASHA_ORDER, DASHA_YEARS, YEAR_DAYS, vimshottari
from .sky import bisect_root, datetime_from_jd, jd_from_datetime, longitude_of

SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
REFS = SEVEN + ["Ascendant"]

# Benefic places: BAV[planet][reference] = houses (counted from the reference) that give a bindu.
BAV = {
    "Sun": {"Sun": [1, 2, 4, 7, 8, 9, 10, 11], "Moon": [3, 6, 10, 11], "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
            "Mercury": [3, 5, 6, 9, 10, 11, 12], "Jupiter": [5, 6, 9, 11], "Venus": [6, 7, 12],
            "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Ascendant": [3, 4, 6, 10, 11, 12]},
    "Moon": {"Sun": [3, 6, 7, 8, 10, 11], "Moon": [1, 3, 6, 7, 10, 11], "Mars": [2, 3, 5, 6, 9, 10, 11],
             "Mercury": [1, 3, 4, 5, 7, 8, 10, 11], "Jupiter": [1, 4, 7, 8, 10, 11, 12], "Venus": [3, 4, 5, 7, 9, 10, 11],
             "Saturn": [3, 5, 6, 11], "Ascendant": [3, 6, 10, 11]},
    "Mars": {"Sun": [3, 5, 6, 10, 11], "Moon": [3, 6, 11], "Mars": [1, 2, 4, 7, 8, 10, 11],
             "Mercury": [3, 5, 6, 11], "Jupiter": [6, 10, 11, 12], "Venus": [6, 8, 11, 12],
             "Saturn": [1, 4, 7, 8, 9, 10, 11], "Ascendant": [1, 3, 6, 10, 11]},
    "Mercury": {"Sun": [5, 6, 9, 11, 12], "Moon": [2, 4, 6, 8, 10, 11], "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
                "Mercury": [1, 3, 5, 6, 9, 10, 11, 12], "Jupiter": [6, 8, 11, 12], "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
                "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Ascendant": [1, 2, 4, 6, 8, 10, 11]},
    "Jupiter": {"Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11], "Moon": [2, 5, 7, 9, 11], "Mars": [1, 2, 4, 7, 8, 10, 11],
                "Mercury": [1, 2, 4, 5, 6, 9, 10, 11], "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11], "Venus": [2, 5, 6, 9, 10, 11],
                "Saturn": [3, 5, 6, 12], "Ascendant": [1, 2, 4, 5, 6, 7, 9, 10, 11]},
    "Venus": {"Sun": [8, 11, 12], "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12], "Mars": [3, 5, 6, 9, 11, 12],
              "Mercury": [3, 5, 6, 9, 11], "Jupiter": [5, 8, 9, 10, 11], "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
              "Saturn": [3, 4, 5, 8, 9, 10, 11], "Ascendant": [1, 2, 3, 4, 5, 8, 9, 11]},
    "Saturn": {"Sun": [1, 2, 4, 7, 8, 10, 11], "Moon": [3, 6, 11], "Mars": [3, 5, 6, 10, 11, 12],
               "Mercury": [6, 8, 9, 10, 11, 12], "Jupiter": [5, 6, 11, 12], "Venus": [6, 11, 12],
               "Saturn": [3, 5, 6, 11], "Ascendant": [1, 3, 4, 6, 10, 11]},
}
CHECKSUMS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54, "Jupiter": 56, "Venus": 52, "Saturn": 39}

# Gochara from the natal Moon: good house -> vedha (blocking) house.
GOCHARA = {
    "Sun": {3: 9, 6: 12, 10: 4, 11: 5},
    "Moon": {1: 5, 3: 9, 6: 12, 7: 2, 10: 4, 11: 8},
    "Mars": {3: 12, 6: 9, 11: 5}, "Saturn": {3: 12, 6: 9, 11: 5}, "Rahu": {3: 12, 6: 9, 11: 5}, "Ketu": {3: 12, 6: 9, 11: 5},
    "Mercury": {2: 5, 4: 3, 6: 9, 8: 1, 10: 8, 11: 12},
    "Jupiter": {2: 12, 5: 4, 7: 3, 9: 10, 11: 8},
    "Venus": {1: 8, 2: 7, 3: 1, 4: 10, 5: 9, 8: 5, 9: 11, 11: 6, 12: 3},
}
NO_VEDHA = [{"Sun", "Saturn"}, {"Moon", "Mercury"}]
YOGINIS = [("Mangala", "Moon", 1), ("Pingala", "Sun", 2), ("Dhanya", "Jupiter", 3), ("Bhramari", "Mars", 4),
           ("Bhadrika", "Mercury", 5), ("Ulka", "Saturn", 6), ("Siddha", "Venus", 7), ("Sankata", "Rahu", 8)]


def _count(from_sign: int, to_sign: int) -> int:
    return (to_sign - from_sign) % 12 + 1


KAKSHYA_LORDS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Ascendant"]
KAKSHYA_SPAN = 30 / 8  # 3 deg 45 min


def contributors(signs: dict[str, int], planet: str, sign: int) -> set[str]:
    """Reference points that give `planet` a bindu in `sign` (its Ashtakavarga, broken down)."""
    return {ref for ref, houses in BAV[planet].items() if _count(signs[ref], sign) in houses}


def kakshya_of(longitude: float) -> tuple[int, str]:
    """Which eighth of its sign a longitude is in, and that slice's ruler."""
    i = min(7, int((longitude % 30) // KAKSHYA_SPAN))
    return i, KAKSHYA_LORDS[i]


def _kakshya_key(planet: str, jd: float) -> tuple[int, int]:
    lon = longitude_of(planet, jd, True)[0]
    return int(lon // 30), kakshya_of(lon)[0]


def kakshya_detail(planet: str, signs: dict[str, int], jd: float, horizon_days: int = 730) -> dict:
    """The transit's current slice, whether its ruler gave a bindu, when it leaves, and (Jupiter, Saturn)
    when it next enters a slice that gives one."""
    step = 0.05 if planet == "Moon" else 0.5 if planet in ("Sun", "Mercury", "Venus", "Mars") else 1.0
    lon = longitude_of(planet, jd, True)[0]
    sign = int(lon // 30)
    idx, lord = kakshya_of(lon)
    gives = contributors(signs, planet, sign)
    key0 = (sign, idx)

    def find(pred, limit: float) -> float | None:
        t = jd
        while t < jd + limit:
            t2 = t + step
            if pred(_kakshya_key(planet, t2)):
                return bisect_root(lambda y: -0.5 if pred(_kakshya_key(planet, y)) else 0.5, t, t2, 1e-4)
            t = t2
        return None

    leaves = find(lambda k: k != key0, horizon_days)
    out = {"index": idx + 1, "lord": lord, "has_bindu": lord in gives, "until": datetime_from_jd(leaves).isoformat() if leaves else None}
    if planet in ("Jupiter", "Saturn") and not out["has_bindu"]:
        def good(k: tuple[int, int]) -> bool:
            return KAKSHYA_LORDS[k[1]] in contributors(signs, planet, k[0])
        nxt = find(good, horizon_days)
        out["next_bindu"] = datetime_from_jd(nxt).isoformat() if nxt else None
    return out


def ashtakavarga(signs: dict[str, int]) -> dict:
    """signs: sign index (0-11) of the seven planets and the Ascendant. Returns BAV per planet and SAV."""
    bav = {}
    for planet, refs in BAV.items():
        row = [0] * 12
        for ref, houses in refs.items():
            for h in houses:
                row[(signs[ref] + h - 1) % 12] += 1
        if sum(row) != CHECKSUMS[planet]:
            raise AssertionError(f"Ashtakavarga checksum failed for {planet}: {sum(row)}")
        bav[planet] = row
    sav = [sum(bav[p][i] for p in SEVEN) for i in range(12)]
    assert sum(sav) == 337
    return {"bav": bav, "sav": sav}


@dataclass
class VedicSeasons:
    moon_sign: str
    ashtakavarga: dict | None
    gochara: list[dict]
    sade_sati: dict
    dashas: dict
    yogini: dict
    warnings: list[str] = field(default_factory=list)
    double_transits: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


JUPITER_ASPECTS = (1, 5, 7, 9)   # counting the sign it sits in as 1
SATURN_ASPECTS = (1, 3, 7, 10)


def touched(planet_sign: int, counts: tuple[int, ...]) -> set[int]:
    """Signs a planet in `planet_sign` occupies or aspects."""
    return {(planet_sign + c - 1) % 12 for c in counts}


def double_signs(jd: float) -> set[int]:
    """Signs both transiting Jupiter and Saturn occupy or aspect at this moment (sidereal)."""
    j = int(longitude_of("Jupiter", jd, True)[0] // 30)
    s = int(longitude_of("Saturn", jd, True)[0] // 30)
    return touched(j, JUPITER_ASPECTS) & touched(s, SATURN_ASPECTS)


def double_transits(chart: BirthChart, now: datetime, years: int = 3) -> dict:
    """Activated signs now, and dated windows for the next few years."""
    moon_idx = int(chart.planet("Moon").longitude // 30)
    lagna_idx = int(chart.ascendant.longitude // 30) if chart.time_known and chart.ascendant is not None else None
    t0 = jd_from_datetime(now)

    def label(sign: int) -> dict:
        return {
            "sign": SIGNS[sign],
            "house_from_lagna": _count(lagna_idx, sign) if lagna_idx is not None else None,
            "house_from_moon": _count(moon_idx, sign),
        }

    # Walk day by day; when the set changes, pin the moment down to about a minute.
    windows: list[dict] = []
    open_: dict[int, float] = {s: t0 for s in double_signs(t0)}
    started_before = set(open_)
    t, cur = t0, set(open_)
    end = t0 + years * YEAR_DAYS
    while t < end:
        t2 = min(t + 1, end)
        nxt = double_signs(t2)
        if nxt != cur:
            for sign in cur ^ nxt:
                was = sign in cur
                x = bisect_root(lambda y, sg=sign, w=was: 0.5 if (sg in double_signs(y)) == w else -0.5, t, t2, 1e-3)
                if was:
                    windows.append({**label(sign), "from": datetime_from_jd(open_.pop(sign)).isoformat(),
                                    "to": datetime_from_jd(x).isoformat(), "ongoing": sign in started_before})
                    started_before.discard(sign)
                else:
                    open_[sign] = x
            cur = nxt
        t = t2
    for sign, a in open_.items():
        windows.append({**label(sign), "from": datetime_from_jd(a).isoformat(), "to": None, "ongoing": sign in started_before})
    windows.sort(key=lambda w: (w["from"], w["sign"]))
    # Exact UTC moments: the page shows them as dates in the person's own time zone (rule 3).
    return {"now": [label(s) for s in sorted(double_signs(t0))], "windows": windows, "years": years,
            "houses_from": "lagna" if lagna_idx is not None else "moon"}


def vedic_seasons(chart: BirthChart, now: datetime) -> VedicSeasons:
    if chart.system != "vedic":
        raise ValueError("Vedic seasons need a Vedic (sidereal) chart")
    p = {x.name: x for x in chart.planets}
    moon = p["Moon"]
    moon_idx = int(moon.longitude // 30)
    birth_dt = datetime.fromisoformat(chart.utc_time)
    birth = jd_from_datetime(birth_dt)
    t_now = jd_from_datetime(now)
    warnings = []

    # Ashtakavarga (needs the Ascendant).
    av = None
    if chart.time_known and chart.ascendant is not None:
        signs = {n: int(p[n].longitude // 30) for n in SEVEN}
        signs["Ascendant"] = int(chart.ascendant.longitude // 30)
        av = ashtakavarga(signs)
    else:
        warnings.append("Birth time unknown: Ashtakavarga needs the Ascendant, so it is left out.")

    # Gochara now, from the natal Moon sign, with vedha.
    transit = {n: int(longitude_of(n, t_now, True)[0] // 30) for n in SEVEN}
    from .soul import mean_node
    rahu = int(mean_node(t_now, True) // 30)
    transit["Rahu"], transit["Ketu"] = rahu, (rahu + 6) % 12
    houses = {n: _count(moon_idx, s) for n, s in transit.items()}
    gochara = []
    for n in SEVEN + ["Rahu", "Ketu"]:
        h = houses[n]
        good = GOCHARA[n]
        status, blocker = "challenging", None
        if h in good:
            status = "favourable"
            vedha_house = good[h]
            for other, oh in houses.items():
                if other != n and oh == vedha_house and {n, other} not in NO_VEDHA and not ({n, other} <= {"Rahu", "Ketu"}):
                    status, blocker = "blocked", other
                    break
        entry = {"planet": n, "sign": SIGNS[transit[n]], "house_from_moon": h, "status": status, "blocked_by": blocker}
        if av and n in av["bav"]:
            entry["bindus"] = av["bav"][n][transit[n]]
            entry["sav"] = av["sav"][transit[n]]
            entry["kakshya"] = kakshya_detail(n, signs, t_now)
        gochara.append(entry)

    # Sade Sati and Dhaiya across life: sidereal Saturn's stays in each sign.
    def sat_sign(t: float) -> int:
        return int(longitude_of("Saturn", t, True)[0] // 30)

    stays: list[tuple[int, float, float]] = []
    t, cur, start = birth, sat_sign(birth), birth
    end = birth + 95 * YEAR_DAYS
    while t < end:
        t2 = t + 10
        s2 = sat_sign(t2)
        if s2 != cur:
            x = bisect_root(lambda y, c=cur: 0.5 if sat_sign(y) == c else -0.5, t, t2, 1e-4)
            stays.append((cur, start, x))
            cur, start = s2, x
        t = t2
    stays.append((cur, start, end))
    phase_of = {12: "rising", 1: "peak", 2: "setting"}
    episodes: list[dict] = []
    dhaiya: list[dict] = []
    for sign, a, b in stays:
        h = _count(moon_idx, sign)
        span = {"sign": SIGNS[sign], "from": datetime_from_jd(a).date().isoformat(), "to": datetime_from_jd(b).date().isoformat()}
        if h in phase_of:
            if not episodes or a - episodes[-1]["_end"] > 400:
                episodes.append({"phases": [], "_end": b})
            episodes[-1]["phases"].append({**span, "phase": phase_of[h]})
            episodes[-1]["_end"] = b
        elif h in (4, 8):
            dhaiya.append({**span, "house": h})
    for e in episodes:
        e["from"], e["to"] = e["phases"][0]["from"], e["phases"][-1]["to"]
        e.pop("_end")
    today = now.date().isoformat()
    current = next(({"phase": ph["phase"], **ph} for e in episodes for ph in e["phases"] if ph["from"] <= today < ph["to"]), None)
    current_dhaiya = next((d for d in dhaiya if d["from"] <= today < d["to"]), None)
    sade = {"episodes": episodes, "current": current, "dhaiya": dhaiya, "current_dhaiya": current_dhaiya,
            "next": next((e for e in episodes if e["from"] > today), None)}
    if not chart.time_known:
        off = moon.longitude % 30
        if min(off, 30 - off) < 6.6:
            warnings.append("Birth time unknown and your Moon was near the edge of a sign, so Sade Sati dates may shift.")

    # Vimshottari with pratyantar inside the running antardasha.
    periods, current_d = vimshottari(moon.longitude, birth_dt, now)
    pratyantar = []
    for maha in periods:
        for antar in maha.sub_periods:
            if antar.start <= today < antar.end:
                a0 = datetime.fromisoformat(antar.start)
                total = (datetime.fromisoformat(antar.end) - a0).days
                i0 = DASHA_ORDER.index(antar.lord)
                t0 = a0
                for k in range(9):
                    lord = DASHA_ORDER[(i0 + k) % 9]
                    length = timedelta(days=total * DASHA_YEARS[lord] / 120)
                    pratyantar.append({"lord": lord, "start": t0.date().isoformat(), "end": (t0 + length).date().isoformat()})
                    t0 += length
    current_p = next((x for x in pratyantar if x["start"] <= today < x["end"]), None)
    dashas = {**current_d, "pratyantar": current_p["lord"] if current_p else None,
              "pratyantar_start": current_p["start"] if current_p else None,
              "pratyantar_end": current_p["end"] if current_p else None, "pratyantars": pratyantar}

    # Yogini dasha (36-year cycle).
    nak = int(moon.longitude / NAKSHATRA_SPAN + 1e-9) % 27 + 1
    first = (nak + 3) % 8
    first = 7 if first == 0 else first - 1          # 1-based remainder -> index; 0 means Sankata
    elapsed = (moon.longitude % NAKSHATRA_SPAN) / NAKSHATRA_SPAN
    yog = []
    t0 = birth_dt - timedelta(days=YOGINIS[first][2] * elapsed * YEAR_DAYS)
    k = first
    while t0 < birth_dt + timedelta(days=100 * YEAR_DAYS):
        name, lord, years = YOGINIS[k % 8]
        t1 = t0 + timedelta(days=years * YEAR_DAYS)
        yog.append({"yogini": name, "lord": lord, "start": t0.date().isoformat(), "end": t1.date().isoformat()})
        t0, k = t1, k + 1
    yogini = {"periods": yog, "current": next((y for y in yog if y["start"] <= today < y["end"]), None)}

    return VedicSeasons(SIGNS[moon_idx], av, gochara, sade, dashas, yogini, warnings, double_transits(chart, now))
