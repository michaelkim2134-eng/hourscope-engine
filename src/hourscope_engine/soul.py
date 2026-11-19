"""Soul Path: karma and purpose themes, computed by rule (rule 1).

See docs/research/karma-and-purpose.md (techniques 1, 2, 3, 5, 7, 9, 10, 11, 13)
and docs/research/vedic-interpretation.md (T8, chara karakas).
- Nodal axis (mean node): sign and house axis, planets on the Nodes, each
  Node's dispositor; nodal returns and reversals through life.
- Saturn as teacher: natal sign and house, its tightest aspect, the Saturn
  cycle (squares, opposition, returns) with every pass, and the current phase.
- Sun-Moon polarity, mission cross (weighted modality), growth planet.
- Vedic: chara karakas (Atmakaraka = soul planet), karakamsa, the four aims.
Framed as growth themes, never fate or spiritual rank.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

import swisseph as swe

from .chart import SIGNS, BirthChart
from .insights import ELEMENT, MODALITY, TRADITIONAL_RULERS, dignity, navamsa_sign, vedic_dignity
from .sky import bisect_root, datetime_from_jd, ephe_flag, jd_from_datetime, longitude_of, signed_diff

PERSONAL = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
OUTER = ["Uranus", "Neptune", "Pluto"]
NODE_ORB = 5.0          # personal planets on a Node
NODE_ORB_OUTER = 3.0
YEARS_AHEAD = 95        # lifetime span for cycles
COMPATIBLE = {frozenset({"fire", "air"}), frozenset({"earth", "water"})}
CHARA_KARAKAS = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka",
                 "Pitrikaraka", "Putrakaraka", "Gnatikaraka", "Darakaraka"]
SATURN_PHASES = [(0, "building"), (90, "testing"), (180, "harvest"), (270, "release")]


def _sep(a: float, b: float) -> float:
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def mean_node(jd: float, sidereal: bool) -> float:
    flags = ephe_flag()
    if sidereal:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags |= swe.FLG_SIDEREAL
    xx, _ = swe.calc_ut(jd, swe.MEAN_NODE, flags)
    return xx[0] % 360


def _node_crossings(target: float, jd0: float, jd1: float, sidereal: bool) -> list[float]:
    """Moments the transiting mean node is exactly at `target` (it moves backwards, ~19 degrees a year)."""
    out = []
    step = 10.0
    t = jd0
    prev = signed_diff(mean_node(t, sidereal) - target, 0.0)
    while t < jd1:
        t2 = min(t + step, jd1)
        cur = signed_diff(mean_node(t2, sidereal) - target, 0.0)
        if abs(prev) < 10 and abs(cur) < 10 and (prev <= 0 < cur or cur <= 0 < prev):
            out.append(bisect_root(lambda x: signed_diff(mean_node(x, sidereal) - target, 0.0), t, t2, 1e-5))
        prev, t = cur, t2
    return out


def _saturn_hits(natal: float, angle: float, jd0: float, jd1: float, sidereal: bool) -> list[float]:
    """Exact moments transiting Saturn is `angle` degrees ahead of its natal place."""
    target = (natal + angle) % 360
    out = []
    t = jd0
    prev = signed_diff(longitude_of("Saturn", t, sidereal)[0] - target, 0.0)
    while t < jd1:
        t2 = min(t + 2.0, jd1)
        cur = signed_diff(longitude_of("Saturn", t2, sidereal)[0] - target, 0.0)
        if abs(prev) < 10 and abs(cur) < 10 and (prev <= 0 < cur or cur <= 0 < prev):
            out.append(bisect_root(lambda x: signed_diff(longitude_of("Saturn", x, sidereal)[0] - target, 0.0), t, t2, 1e-5))
        prev, t = cur, t2
    return out


def _group_passes(times: list[float], gap: float = 300.0) -> list[list[float]]:
    """Retrograde loops give up to three exact passes; group passes less than `gap` days apart."""
    groups: list[list[float]] = []
    for t in sorted(times):
        if groups and t - groups[-1][-1] < gap:
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups


@dataclass
class SoulPath:
    system: str
    nodes: dict
    node_contacts: list[dict]
    node_dispositors: dict
    nodal_cycle: list[dict]
    saturn: dict
    polarity: dict
    mission: dict
    growth_planet: dict | None
    vedic: dict | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def soul_path(chart: BirthChart, now: datetime) -> SoulPath:
    sidereal = chart.system == "vedic"
    iso = lambda jd: datetime_from_jd(jd).isoformat()  # noqa: E731
    birth_dt = datetime.fromisoformat(chart.utc_time)
    birth = jd_from_datetime(birth_dt)
    jd_now = jd_from_datetime(now)
    end = birth + YEARS_AHEAD * 365.2422
    has_houses = chart.time_known and chart.ascendant is not None
    dig = (lambda p: vedic_dignity(p.name, p.longitude)) if sidereal else (lambda p: dignity(p.name, p.sign))
    warnings = [] if has_houses else ["Birth time unknown: houses, the house cross and the four aims are left out."]

    # 1. Nodal axis (mean node; the chart's own North Node / Rahu position).
    nn = chart.planet("Rahu" if sidereal else "North Node")
    sn_lon = (nn.longitude + 180) % 360
    sn_sign = SIGNS[int(sn_lon // 30)]
    nn_house = nn.house if has_houses else None
    sn_house = ((nn_house + 5) % 12) + 1 if nn_house else None
    nodes = {"north": {"sign": nn.sign, "degree": round(nn.sign_degree, 2), "house": nn_house},
             "south": {"sign": sn_sign, "degree": round(sn_lon % 30, 2), "house": sn_house},
             "axis": f"{nn.sign}-{sn_sign}"}

    # 2. Planets on the Nodes.
    contacts = []
    for p in chart.planets:
        if p.name not in PERSONAL + OUTER:
            continue
        orb = NODE_ORB_OUTER if p.name in OUTER else NODE_ORB
        for node, lon in (("north", nn.longitude), ("south", sn_lon)):
            d = _sep(p.longitude, lon)
            if d <= orb:
                contacts.append({"planet": p.name, "node": node, "orb": round(d, 2)})

    # 13. Node dispositors (the planet ruling each Node's sign).
    def dispositor(sign: str) -> dict:
        lord = TRADITIONAL_RULERS[sign]
        lp = chart.planet(lord)
        return {"lord": lord, "sign": lp.sign, "house": lp.house if has_houses else None, "dignity": dig(lp)}

    disp = {"north": dispositor(nn.sign), "south": dispositor(sn_sign)}

    # 3. Nodal returns (node back on its natal place) and reversals (on the natal South Node).
    cycle = [{"kind": "return", "at": iso(t), "age": round((t - birth) / 365.2422, 1)}
             for t in _node_crossings(nn.longitude, birth + 3000, end, sidereal)]
    cycle += [{"kind": "reversal", "at": iso(t), "age": round((t - birth) / 365.2422, 1)}
              for t in _node_crossings(sn_lon, birth + 1500, end, sidereal)]
    cycle.sort(key=lambda e: e["at"])

    # 5. Saturn as teacher.
    sat = chart.planet("Saturn")
    sat_aspects = sorted([a for a in chart.aspects if "Saturn" in (a.a, a.b)], key=lambda a: a.orb)
    tight = sat_aspects[0] if sat_aspects else None
    events = []
    names = {0: "return", 90: "opening square", 180: "opposition", 270: "closing square"}
    for angle, label in names.items():
        start = birth + (3000 if angle == 0 else 300)
        for passes in _group_passes(_saturn_hits(sat.longitude, angle, start, end, sidereal)):
            events.append({"kind": label, "passes": [iso(t) for t in passes],
                           "age": round((passes[0] - birth) / 365.2422, 1)})
    events.sort(key=lambda e: e["passes"][0])
    elong = (longitude_of("Saturn", jd_now, sidereal)[0] - sat.longitude) % 360
    phase = [name for lo, name in SATURN_PHASES if elong >= lo][-1]
    saturn = {
        "sign": sat.sign, "house": sat.house if has_houses else None, "dignity": dig(sat), "retrograde": sat.retrograde,
        "tightest_aspect": {"with": tight.b if tight.a == "Saturn" else tight.a, "kind": tight.kind, "orb": round(tight.orb, 2)} if tight else None,
        "cycle": events,
        "phase": {"name": phase, "percent": round(elong / 360 * 100, 1)},
        "next": next((e for e in events if e["passes"][-1] > iso(jd_now)), None),
    }

    # 7. Sun-Moon polarity.
    sun, moon = chart.planet("Sun"), chart.planet("Moon")
    e1, e2 = ELEMENT[sun.sign], ELEMENT[moon.sign]
    harmony = "same" if e1 == e2 else "compatible" if frozenset({e1, e2}) in COMPATIBLE else "tension"
    polarity = {"sun": sun.sign, "moon": moon.sign, "elements": [e1, e2],
                "modes": [MODALITY[sun.sign], MODALITY[moon.sign]], "harmony": harmony}

    # 9. Mission cross: weighted modality count (Sun, Moon, Ascendant 3; Mercury-Saturn 2; outers 1).
    weights = {"Sun": 3, "Moon": 3, "Mercury": 2, "Venus": 2, "Mars": 2, "Jupiter": 2, "Saturn": 2,
               "Uranus": 1, "Neptune": 1, "Pluto": 1}
    signs = {p.name: p.sign for p in chart.planets if p.name in weights}
    if chart.ascendant is not None and has_houses:
        signs["Ascendant"] = chart.ascendant.sign
        weights["Ascendant"] = 3
    sign_cross = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for name, s in signs.items():
        sign_cross[MODALITY[s]] += weights[name]
    house_cross = None
    if has_houses:
        house_cross = {"angular": 0, "succedent": 0, "cadent": 0}
        for p in chart.planets:
            if p.name in weights and p.house:
                house_cross[["angular", "succedent", "cadent"][(p.house - 1) % 3]] += weights[p.name]
    mission = {"sign_cross": sign_cross, "dominant": max(sign_cross, key=sign_cross.get),
               "house_cross": house_cross, "dominant_house": max(house_cross, key=house_cross.get) if house_cross else None}

    # 10. Growth planet: the planet (other than the lights) with the most emphasis.
    angles = [x.longitude for x in (chart.ascendant, chart.midheaven) if x is not None] if has_houses else []
    if has_houses:
        angles += [(a + 180) % 360 for a in list(angles)]
    asc_ruler = TRADITIONAL_RULERS[chart.ascendant.sign] if has_houses else None
    scores = {}
    for p in chart.planets:
        if p.name not in PERSONAL[2:] + OUTER:
            continue
        d = dig(p)
        s = 0.0
        if d in ("domicile", "exaltation", "own sign", "moolatrikona", "deep exaltation"):
            s += 3
        elif d in ("detriment", "fall", "debilitation", "deep debilitation"):
            s -= 2
        if any(_sep(p.longitude, a) <= 8 for a in angles):
            s += 3
        s += sum(1 for a in chart.aspects if p.name in (a.a, a.b) and {"Sun", "Moon"} & {a.a, a.b})
        if p.name == asc_ruler:
            s += 2
        if abs(p.speed) < 0.02 and p.name not in ("Sun", "Moon"):
            s += 2   # stationary at birth
        scores[p.name] = s
    growth = None
    if scores:
        best = max(scores, key=lambda k: (scores[k], k in PERSONAL))
        bp = chart.planet(best)
        growth = {"planet": best, "score": scores[best], "sign": bp.sign, "house": bp.house if has_houses else None}

    # Vedic: chara karakas and the four aims.
    vedic = None
    if sidereal:
        degs = [(p.name, p.sign_degree) for p in chart.planets if p.name in PERSONAL]
        degs.append(("Rahu", 30 - nn.sign_degree))
        degs.sort(key=lambda x: -x[1])
        karakas = [{"karaka": CHARA_KARAKAS[i], "planet": n, "degree": round(d, 2)} for i, (n, d) in enumerate(degs)]
        ties = [f"{a['planet']} and {b['planet']}" for a, b in zip(karakas, karakas[1:]) if a["degree"] - b["degree"] < 1.0]
        ak = chart.planet(karakas[0]["planet"]) if karakas[0]["planet"] != "Rahu" else nn
        aims = None
        if has_houses:
            aw = {"dharma": 0, "artha": 0, "kama": 0, "moksha": 0}
            order = ["dharma", "artha", "kama", "moksha"]
            for p in chart.planets:
                if p.name in weights and p.house:
                    aw[order[(p.house - 1) % 4]] += weights[p.name]
            total = sum(aw.values()) or 1
            aims = {k: round(v / total * 100) for k, v in aw.items()}
        vedic = {"karakas": karakas, "atmakaraka": karakas[0]["planet"], "karakamsa": navamsa_sign(ak.longitude),
                 "close_degrees": ties, "aims": aims}

    return SoulPath(system=chart.system, nodes=nodes, node_contacts=contacts, node_dispositors=disp,
                    nodal_cycle=cycle, saturn=saturn, polarity=polarity, mission=mission,
                    growth_planet=growth, vedic=vedic, warnings=warnings)
