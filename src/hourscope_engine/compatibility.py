"""Compatibility Studio: two people's charts compared.

See docs/research/relationships-and-places.md (A1-A5, sections 6 and 7).
- Ashtakoota / Guna Milan (36 points) from the two sidereal Moons. The
  one-directional kootas (Varna, Vashya, Gana) are averaged both ways so the
  score works for any couple or friendship; classical exceptions are flagged,
  never silently rescored. With an unknown birth time the Moon at the start and
  end of the birth day gives a score range (rule 4).
- Manglik (Mars from the Lagna, Moon and Venus; houses 1, 4, 7, 8, 12) with
  the classical cancellations, for each person and for the pair.
- Western synastry: aspects both ways (6 degrees for lights and angles,
  4 for planets, 2 for the quincunx), tagged impact / ease / adjust.
- Karmic contacts: Saturn on the other's Sun, Moon, Venus or Ascendant; personal
  planets on the other's Nodes.
- Composite: shorter-arc midpoints of the personal planets.
Bands, never verdicts; no fatalism (section 7).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, time
from itertools import product

from .numerology import NUMBER_FAMILIES, life_path, life_path_pair
from .chart import NAKSHATRA_SPAN, NAKSHATRAS, SIGNS, BirthChart, compute_chart
from .insights import NATURAL_ENEMIES, TRADITIONAL_RULERS
from .electional import _ord
from .planet_cards import NATURAL_FRIENDS

PERSONAL = ["Sun", "Moon", "Mercury", "Venus", "Mars"]
PLANETS = PERSONAL + ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "quincunx": 150, "opposition": 180}
TAG = {"conjunction": "impact", "opposition": "impact", "square": "impact", "trine": "ease", "sextile": "ease", "quincunx": "adjust"}

VARNA_RANK = {"water": 4, "fire": 3, "earth": 2, "air": 1}
ELEMENT = {s: e for s, e in zip(SIGNS, ["fire", "earth", "air", "water"] * 3)}
VASHYA_GROUPS = ["quadruped", "human", "water", "wild", "insect"]
VASHYA_MATRIX = [   # standard table, symmetric
    [2, 1, 1, 0.5, 1],
    [1, 2, 0.5, 0, 1],
    [1, 0.5, 2, 1, 1],
    [0.5, 0, 1, 2, 0],
    [1, 1, 1, 0, 2],
]
YONI_ANIMALS = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat", "Cow", "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion"]
YONI_OF = {  # nakshatra -> animal
    "Ashwini": "Horse", "Shatabhisha": "Horse", "Bharani": "Elephant", "Revati": "Elephant", "Krittika": "Sheep",
    "Pushya": "Sheep", "Rohini": "Serpent", "Mrigashira": "Serpent", "Ardra": "Dog", "Mula": "Dog",
    "Punarvasu": "Cat", "Ashlesha": "Cat", "Magha": "Rat", "Purva Phalguni": "Rat", "Uttara Phalguni": "Cow",
    "Uttara Bhadrapada": "Cow", "Hasta": "Buffalo", "Swati": "Buffalo", "Chitra": "Tiger", "Vishakha": "Tiger",
    "Anuradha": "Deer", "Jyeshtha": "Deer", "Purva Ashadha": "Monkey", "Shravana": "Monkey",
    "Uttara Ashadha": "Mongoose", "Dhanishta": "Lion", "Purva Bhadrapada": "Lion",
}
YONI_MATRIX = [   # standard table (order of YONI_ANIMALS), symmetric; enemies score 0
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1],
    [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1],
    [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1],
    [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2],
    [1, 2, 3, 1, 2, 2, 2, 4, 3, 0, 3, 2, 2, 1],
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1],
    [1, 1, 1, 2, 1, 1, 2, 0, 1, 4, 1, 1, 2, 1],
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1],
    [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2],
    [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4],
]
DEVA = {"Ashwini", "Mrigashira", "Punarvasu", "Pushya", "Hasta", "Swati", "Anuradha", "Shravana", "Revati"}
MANUSHYA = {"Bharani", "Rohini", "Ardra", "Purva Phalguni", "Purva Ashadha", "Purva Bhadrapada",
            "Uttara Phalguni", "Uttara Ashadha", "Uttara Bhadrapada"}
GANA_MATRIX = {("deva", "deva"): 6, ("deva", "manushya"): 6, ("deva", "rakshasa"): 1,
               ("manushya", "deva"): 5, ("manushya", "manushya"): 6, ("manushya", "rakshasa"): 0,
               ("rakshasa", "deva"): 1, ("rakshasa", "manushya"): 0, ("rakshasa", "rakshasa"): 6}
MAX = {"varna": 1, "vashya": 2, "tara": 3, "yoni": 4, "graha_maitri": 5, "gana": 6, "bhakoot": 7, "nadi": 8}


def _sep(a: float, b: float) -> float:
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def vashya_group(lon: float) -> str:
    sign = SIGNS[int(lon // 30)]
    deg = lon % 30
    if sign in ("Aries", "Taurus") or (sign == "Sagittarius" and deg >= 15) or (sign == "Capricorn" and deg < 15):
        return "quadruped"
    if sign in ("Gemini", "Virgo", "Libra", "Aquarius") or (sign == "Sagittarius" and deg < 15):
        return "human"
    if sign in ("Cancer", "Pisces") or (sign == "Capricorn" and deg >= 15):
        return "water"
    return "wild" if sign == "Leo" else "insect"


def gana_of(nak: str) -> str:
    return "deva" if nak in DEVA else "manushya" if nak in MANUSHYA else "rakshasa"


def nadi_of(n: int) -> str:   # n = 1..27
    r = n % 6
    return "adi" if r in (0, 1) else "madhya" if r in (2, 5) else "antya"


def relation(of: str, to: str) -> str:
    if of == to or to in NATURAL_FRIENDS[of]:
        return "friend"
    return "enemy" if to in NATURAL_ENEMIES[of] else "neutral"


def ashtakoota(moon_a: float, moon_b: float) -> dict:
    """The eight kootas from two sidereal Moon longitudes."""
    na, nb = int(moon_a / NAKSHATRA_SPAN + 1e-9) % 27, int(moon_b / NAKSHATRA_SPAN + 1e-9) % 27
    sa, sb = int(moon_a // 30), int(moon_b // 30)
    pada_a, pada_b = int((moon_a % NAKSHATRA_SPAN) / (NAKSHATRA_SPAN / 4)) + 1, int((moon_b % NAKSHATRA_SPAN) / (NAKSHATRA_SPAN / 4)) + 1
    nak_a, nak_b = NAKSHATRAS[na], NAKSHATRAS[nb]
    sign_a, sign_b = SIGNS[sa], SIGNS[sb]
    lord_a, lord_b = TRADITIONAL_RULERS[sign_a], TRADITIONAL_RULERS[sign_b]

    def varna(x: str, y: str) -> float:
        return 1.0 if VARNA_RANK[ELEMENT[x]] >= VARNA_RANK[ELEMENT[y]] else 0.0

    def tara_one(f: int, t: int) -> float:
        return 0.0 if ((t - f) % 27 + 1) % 9 in (3, 5, 7) else 1.5

    rel = sorted([relation(lord_a, lord_b), relation(lord_b, lord_a)])
    maitri = {("friend", "friend"): 5, ("friend", "neutral"): 4, ("neutral", "neutral"): 3,
              ("enemy", "friend"): 1, ("enemy", "neutral"): 0.5, ("enemy", "enemy"): 0}[tuple(rel)]
    if lord_a == lord_b:
        maitri = 5
    d = (sb - sa) % 12 + 1
    bhakoot = 0 if {d, (sa - sb) % 12 + 1} in ({2, 12}, {5, 9}, {6, 8}) else 7
    ga, gb = gana_of(nak_a), gana_of(nak_b)
    parts = {
        "varna": (varna(sign_a, sign_b) + varna(sign_b, sign_a)) / 2,
        "vashya": VASHYA_MATRIX[VASHYA_GROUPS.index(vashya_group(moon_a))][VASHYA_GROUPS.index(vashya_group(moon_b))],
        "tara": tara_one(na, nb) + tara_one(nb, na),
        "yoni": YONI_MATRIX[YONI_ANIMALS.index(YONI_OF[nak_a])][YONI_ANIMALS.index(YONI_OF[nak_b])],
        "graha_maitri": maitri,
        "gana": (GANA_MATRIX[(ga, gb)] + GANA_MATRIX[(gb, ga)]) / 2,
        "bhakoot": bhakoot,
        "nadi": 0 if nadi_of(na + 1) == nadi_of(nb + 1) else 8,
    }
    notes = []
    if parts["nadi"] == 0 and ((sa == sb and na != nb) or (na == nb and pada_a != pada_b)):
        notes.append("nadi: same nadi, but a classical exception applies (same sign with different stars, or same star with different padas)")
    if bhakoot == 0 and (lord_a == lord_b or relation(lord_a, lord_b) == "friend" == relation(lord_b, lord_a)):
        notes.append("bhakoot: the sign distance scores 0, but the two Moon-sign lords are friends, which classical texts treat as softening it")
    total = round(sum(parts.values()), 1)
    band = "excellent" if total >= 33 else "good" if total >= 25 else "average" if total >= 18 else "effortful"
    return {
        "a": {"nakshatra": nak_a, "pada": pada_a, "sign": sign_a, "yoni": YONI_OF[nak_a], "gana": ga, "nadi": nadi_of(na + 1), "vashya": vashya_group(moon_a)},
        "b": {"nakshatra": nak_b, "pada": pada_b, "sign": sign_b, "yoni": YONI_OF[nak_b], "gana": gb, "nadi": nadi_of(nb + 1), "vashya": vashya_group(moon_b)},
        "parts": parts, "max": MAX, "total": total, "band": band, "notes": notes,
    }


def manglik(chart: BirthChart) -> dict:
    """Mars from the Lagna, Moon and Venus (Vedic whole-sign houses), with classical cancellations."""
    p = {x.name: x for x in chart.planets}
    mars = p["Mars"]
    ms = SIGNS.index(mars.sign)
    refs = {"Venus": SIGNS.index(p["Venus"].sign), "Moon": SIGNS.index(p["Moon"].sign)}
    if chart.time_known and chart.ascendant is not None:
        refs["Lagna"] = SIGNS.index(chart.ascendant.sign)
    hits = {ref: (ms - s) % 12 + 1 for ref, s in refs.items()}
    from_points = [ref for ref, h in hits.items() if h in (1, 4, 7, 8, 12)]
    cancel = []
    if mars.sign in ("Aries", "Scorpio", "Capricorn"):
        cancel.append(f"Mars is strong in its own or exaltation sign ({mars.sign})")
    special = {("Aries", 1), ("Scorpio", 4), ("Capricorn", 7), ("Cancer", 8), ("Sagittarius", 12)}
    for ref in from_points:
        if (mars.sign, hits[ref]) in special:
            cancel.append(f"Mars in {mars.sign} in the {_ord(hits[ref])} from the {ref} is a classical exception")
    for other in ("Jupiter", "Moon", "Rahu"):
        if other in p and p[other].sign == mars.sign:
            cancel.append(f"Mars shares a sign with {other}")
    js = SIGNS.index(p["Jupiter"].sign)
    if (ms - js) % 12 + 1 in (5, 7, 9):
        cancel.append("Jupiter aspects Mars")
    if "Lagna" in refs and (SIGNS.index(p["Moon"].sign) - refs["Lagna"]) % 12 + 1 in (1, 4, 7, 10):
        cancel.append("the Moon is in an angle from the Lagna")
    status = "none" if not from_points else "cancelled" if cancel else "present"
    return {"status": status, "from": from_points, "houses": hits, "cancellations": cancel if from_points else []}


@dataclass
class Compatibility:
    ashtakoota: dict
    range: dict | None
    manglik: dict
    synastry: list[dict]
    karmic: list[dict]
    composite: dict
    warnings: list[str] = field(default_factory=list)
    numbers: dict = field(default_factory=dict)  # Life Paths and how they pair

    def to_dict(self) -> dict:
        return asdict(self)


def _moons_for_day(birth_date: date, lat: float, lon: float, tz: str | None) -> list[float]:
    out = []
    for t in (time(0, 0), time(23, 59)):
        out.append(compute_chart(birth_date, t, lat, lon, tz, "vedic").planet("Moon").longitude)
    return out


def _numbers(a: dict, b: dict) -> dict:
    la, lb = life_path(a["birth_date"]), life_path(b["birth_date"])
    pair = life_path_pair(la, lb)
    fa, fb = NUMBER_FAMILIES[pair[0]], NUMBER_FAMILIES[pair[1]]
    return {"a_life_path": la, "b_life_path": lb, "pair": list(pair), "same_family": fa == fb, "families": [fa, fb]}


def compatibility(a: dict, b: dict) -> Compatibility:
    """a, b: {birth_date, birth_time, latitude, longitude, timezone}."""
    va = compute_chart(a["birth_date"], a["birth_time"], a["latitude"], a["longitude"], a.get("timezone"), "vedic")
    vb = compute_chart(b["birth_date"], b["birth_time"], b["latitude"], b["longitude"], b.get("timezone"), "vedic")
    wa = compute_chart(a["birth_date"], a["birth_time"], a["latitude"], a["longitude"], a.get("timezone"), "western")
    wb = compute_chart(b["birth_date"], b["birth_time"], b["latitude"], b["longitude"], b.get("timezone"), "western")
    warnings = []
    ak = ashtakoota(va.planet("Moon").longitude, vb.planet("Moon").longitude)

    # Unknown birth time: score every combination of the Moon at the start and end of the day.
    rng = None
    if not va.time_known or not vb.time_known:
        ma = _moons_for_day(a["birth_date"], a["latitude"], a["longitude"], a.get("timezone")) if not va.time_known else [va.planet("Moon").longitude]
        mb = _moons_for_day(b["birth_date"], b["latitude"], b["longitude"], b.get("timezone")) if not vb.time_known else [vb.planet("Moon").longitude]
        totals = [ashtakoota(x, y)["total"] for x, y in product(ma, mb)]
        rng = {"min": min(totals), "max": max(totals)}
        if rng["min"] != rng["max"]:
            warnings.append("A birth time is unknown and the Moon changed star or sign that day, so the score is shown as a range.")

    ma_, mb_ = manglik(va), manglik(vb)
    pair_note = None
    if ma_["status"] == "present" and mb_["status"] == "present":
        pair_note = "Both charts carry the Mars placement, which classical texts treat as balancing each other."
    mang = {"a": ma_, "b": mb_, "pair_note": pair_note}

    def points(c: BirthChart) -> dict[str, float]:
        pts = {x.name: x.longitude for x in c.planets if x.name in PLANETS + ["North Node"]}
        if c.time_known and c.ascendant is not None:
            pts["Ascendant"] = c.ascendant.longitude
            if c.midheaven is not None:
                pts["Midheaven"] = c.midheaven.longitude
        return pts

    pa, pb = points(wa), points(wb)
    syn = []
    for (na_, la), (nb_, lb) in product(pa.items(), pb.items()):
        if "North Node" in (na_, nb_):
            continue
        for kind, angle in ASPECTS.items():
            big = {"Sun", "Moon", "Ascendant", "Midheaven"}
            orb = 2.0 if kind == "quincunx" else 6.0 if (na_ in big or nb_ in big) else 4.0
            o = abs(_sep(la, lb) - angle)
            if o <= orb:
                weight = (2 if na_ in PERSONAL + ["Ascendant"] else 1) + (2 if nb_ in PERSONAL + ["Ascendant"] else 1)
                syn.append({"a": na_, "b": nb_, "kind": kind, "orb": round(o, 2), "tag": TAG[kind], "weight": weight})
    syn.sort(key=lambda x: (-x["weight"], x["orb"]))
    syn = syn[:24]

    karmic = []
    for who, (sat, other) in {"a": (pa["Saturn"], pb), "b": (pb["Saturn"], pa)}.items():
        for target in ("Sun", "Moon", "Venus", "Ascendant"):
            if target in other:
                for kind in ("conjunction", "square", "opposition"):
                    o = abs(_sep(sat, other[target]) - ASPECTS[kind])
                    if o <= 5:
                        karmic.append({"type": "saturn", "from": who, "planet": "Saturn", "kind": kind, "target": target, "orb": round(o, 2)})
    for who, (mine, other) in {"a": (pa, pb), "b": (pb, pa)}.items():
        node = other.get("North Node")
        if node is None:
            continue
        for planet in PERSONAL:
            for side, lon in (("north", node), ("south", (node + 180) % 360)):
                o = _sep(mine[planet], lon)
                if o <= 4:
                    karmic.append({"type": "node", "from": who, "planet": planet, "kind": "conjunction", "target": f"{side} node", "orb": round(o, 2)})

    def midpoint(x: float, y: float) -> float:
        d = ((y - x + 540) % 360) - 180
        return (x + d / 2) % 360

    comp = {n: SIGNS[int(midpoint(pa[n], pb[n]) // 30)] for n in PERSONAL + ["Jupiter", "Saturn"]}
    if "Ascendant" in pa and "Ascendant" in pb:
        comp["Ascendant"] = SIGNS[int(midpoint(pa["Ascendant"], pb["Ascendant"]) // 30)]

    return Compatibility(ak, rng, mang, syn, karmic, comp, warnings, numbers=_numbers(a, b))
