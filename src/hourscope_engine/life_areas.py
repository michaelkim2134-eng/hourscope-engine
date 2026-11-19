"""Life Areas and your rising sign's cast.

See docs/research/vedic-interpretation.md (T3 functional nature, T4 lord-in-house
matrix and parivartana, T5 Vedic aspects).
- For each of the 12 houses: sign, lord, where the lord sits (house, sign,
  dignity), occupants, class (kendra/trikona/dusthana/upachaya), natural
  significator, and (Vedic) which planets aspect it.
- Parivartana: two planets in each other's signs, classed maha/khala/dainya.
- Vedic cast: each planet's role for the rising sign (yogakaraka, ally,
  mixed, neutral, teacher), from the houses it rules.
Needs a birth time (houses); without one the result is empty with a warning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .chart import SIGNS, BirthChart
from .insights import TRADITIONAL_RULERS, dignity, vedic_dignity

CLASSICAL = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
KENDRA, TRIKONA, DUSTHANA, UPACHAYA = {1, 4, 7, 10}, {1, 5, 9}, {6, 8, 12}, {3, 6, 10, 11}
# Natural significators (karakas) of each house (Parashara, simplified).
KARAKA = {1: ["Sun"], 2: ["Jupiter"], 3: ["Mars"], 4: ["Moon"], 5: ["Jupiter"], 6: ["Mars", "Saturn"],
          7: ["Venus"], 8: ["Saturn"], 9: ["Jupiter", "Sun"], 10: ["Sun", "Mercury"], 11: ["Jupiter"], 12: ["Saturn"]}
# Vedic special aspects: houses counted from the planet (the 7th applies to all).
SPECIAL_ASPECTS = {"Mars": (4, 8), "Jupiter": (5, 9), "Saturn": (3, 10)}


def _count(from_sign: str, to_sign: str) -> int:
    return (SIGNS.index(to_sign) - SIGNS.index(from_sign)) % 12 + 1


def area_class(house: int) -> list[str]:
    out = []
    if house in KENDRA:
        out.append("kendra")
    if house in TRIKONA:
        out.append("trikona")
    if house in DUSTHANA:
        out.append("dusthana")
    if house in UPACHAYA:
        out.append("upachaya")
    return out


def functional_role(planet: str, ruled: set[int]) -> str:
    """Role of a planet for the rising sign, from the houses it rules (T3)."""
    bad = {3, 6, 8, 11}          # 2nd and 12th take the colour of the other house
    if 1 in ruled:
        return "ally"             # the chart ruler is always on your side
    if ruled & {4, 7, 10} and ruled & {5, 9}:
        return "yogakaraka"
    if ruled & {5, 9}:
        return "mixed" if ruled & bad else "ally"
    if 8 in ruled or ruled & {3, 6, 11}:
        return "teacher"
    if ruled & {4, 7, 10}:
        return "neutral"          # benefics lose some goodness ruling angles; malefics improve
    return "neutral"


def vedic_aspects(planet: str, sign: str) -> list[str]:
    """Signs a planet aspects (Parashara graha drishti; nodes excluded)."""
    counts = (7,) + SPECIAL_ASPECTS.get(planet, ())
    return [SIGNS[(SIGNS.index(sign) + c - 1) % 12] for c in counts]


@dataclass
class LifeAreas:
    system: str
    rising: str | None
    houses: list[dict] = field(default_factory=list)
    cast: list[dict] = field(default_factory=list)          # Vedic only
    exchanges: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def life_areas(chart: BirthChart) -> LifeAreas:
    vedic = chart.system == "vedic"
    if chart.ascendant is None or not chart.time_known:
        return LifeAreas(chart.system, None, warnings=["Life Areas need a birth time, because houses depend on the exact moment."])
    rising = chart.ascendant.sign
    planets = {p.name: p for p in chart.planets}
    dig = (lambda p: vedic_dignity(p.name, p.longitude)) if vedic else (lambda p: dignity(p.name, p.sign))

    # Sign on each house: Vedic whole sign from the rising sign; Western, the sign on the Placidus cusp.
    if vedic or not chart.house_cusps:
        signs = [SIGNS[(SIGNS.index(rising) + i) % 12] for i in range(12)]
    else:
        signs = [SIGNS[int(c // 30) % 12] for c in chart.house_cusps]

    aspects_to: dict[str, list[str]] = {s: [] for s in SIGNS}
    if vedic:
        for name in CLASSICAL:
            for s in vedic_aspects(name, planets[name].sign):
                aspects_to[s].append(name)

    houses = []
    for i, sign in enumerate(signs):
        h = i + 1
        lord = TRADITIONAL_RULERS[sign]
        lp = planets[lord]
        occupants = [p.name for p in chart.planets if p.house == h and p.name not in ("South Node",)]
        houses.append({
            "house": h, "sign": sign, "lord": lord,
            "lord_house": lp.house, "lord_sign": lp.sign, "lord_dignity": dig(lp),
            "occupants": occupants, "class": area_class(h), "karakas": KARAKA[h],
            "aspected_by": aspects_to[sign] if vedic else [],
        })

    # Parivartana: A in B's sign and B in A's sign.
    exchanges = []
    for a, b in ((x, y) for i, x in enumerate(CLASSICAL) for y in CLASSICAL[i + 1:]):
        pa, pb = planets[a], planets[b]
        if TRADITIONAL_RULERS[pa.sign] == b and TRADITIONAL_RULERS[pb.sign] == a:
            hs = {pa.house, pb.house}
            kind = "dainya" if hs & DUSTHANA else "khala" if 3 in hs else "maha"
            exchanges.append({"planets": [a, b], "houses": sorted(x for x in hs if x), "kind": kind})

    cast = []
    if vedic:
        for name in CLASSICAL:
            ruled = {i + 1 for i, s in enumerate(signs) if TRADITIONAL_RULERS[s] == name}
            p = planets[name]
            cast.append({"planet": name, "rules": sorted(ruled), "role": functional_role(name, ruled),
                         "house": p.house, "sign": p.sign, "dignity": dig(p), "natural_benefic": name in NATURAL_BENEFICS})
        order = {"yogakaraka": 0, "ally": 1, "mixed": 2, "neutral": 3, "teacher": 4}
        cast.sort(key=lambda c: (order[c["role"]], CLASSICAL.index(c["planet"])))

    return LifeAreas(chart.system, rising, houses, cast, exchanges)
