"""Planet report cards and "who runs your chart".

See docs/research/western-depth-and-timing.md (3.7-3.11) and
docs/research/vedic-interpretation.md (T1, T2, T6, T10).
For each of the seven classical planets:
- comfort: essential dignity. Western: five layers on Lilly's scale
  (domicile 5, exaltation 4, triplicity 3, term 2, face 1; detriment -5,
  fall -4; peregrine = none of the five). Vedic: Parashara dignity, the
  sign lord's natural friendship, and vargottama.
- ability: accidental strength (house type, closeness to an angle, motion,
  cazimi / combust / under the beams, and sect for Western charts).
- boss: its dispositor; guests: reception.
Chart-wide: chart ruler, dispositor chains with the final dispositor (or loops),
mutual receptions, ranked keynotes and the repeating theme ("alphabet" letter).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .chart import SIGNS, BirthChart
from .insights import (
    COMBUSTION_ORB, COMBUSTION_ORB_RETRO, EXALTATION, NATURAL_ENEMIES, TRADITIONAL_RULERS,
    dignity, navamsa_sign, vedic_dignity,
)

CLASSICAL = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
# Egyptian terms: (planet, upper bound in degrees) for each sign.
TERMS = {
    "Aries": [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    "Taurus": [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    "Gemini": [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    "Cancer": [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    "Leo": [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    "Virgo": [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    "Libra": [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    "Scorpio": [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    "Sagittarius": [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    "Capricorn": [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    "Aquarius": [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    "Pisces": [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
}
CHALDEAN = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]   # faces from 0 Aries
TRIPLICITY = {"fire": ("Sun", "Jupiter"), "earth": ("Venus", "Moon"), "air": ("Saturn", "Mercury"), "water": ("Venus", "Mars")}
ELEMENT_OF = {s: e for s, e in zip(SIGNS, ["fire", "earth", "air", "water"] * 3)}
MEAN_SPEED = {"Sun": 0.9856, "Moon": 13.176, "Mercury": 1.383, "Venus": 1.2, "Mars": 0.524, "Jupiter": 0.083, "Saturn": 0.034}
NATURAL_FRIENDS = {"Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"}, "Mars": {"Sun", "Moon", "Jupiter"},
                   "Mercury": {"Sun", "Venus"}, "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
                   "Saturn": {"Mercury", "Venus"}}
DIURNAL = {"Sun", "Jupiter", "Saturn"}
NOCTURNAL = {"Moon", "Venus", "Mars"}
# Herring's alphabet: letter n = the nth sign, its (modern) ruler and the nth house.
LETTER_PLANET = {1: "Mars", 2: "Venus", 3: "Mercury", 4: "Moon", 5: "Sun", 6: "Mercury", 7: "Venus",
                 8: "Pluto", 9: "Jupiter", 10: "Saturn", 11: "Uranus", 12: "Neptune"}


def _sep(a: float, b: float) -> float:
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def term_ruler(sign: str, deg: float) -> str:
    return next(p for p, upper in TERMS[sign] if deg < upper)


def face_ruler(lon: float) -> str:
    return CHALDEAN[int((lon % 360) // 10) % 7]


def essential_layers(planet: str, lon: float, day: bool | None) -> dict:
    """Western five-layer dignity with Lilly's points."""
    sign = SIGNS[int(lon // 30)]
    deg = lon % 30
    layers, score = [], 0
    base = dignity(planet, sign)
    if base == "domicile":
        layers.append("domicile"); score += 5          # noqa: E702
    elif base == "exaltation":
        layers.append("exaltation"); score += 4        # noqa: E702
    elif base == "detriment":
        layers.append("detriment"); score -= 5         # noqa: E702
    elif base == "fall":
        layers.append("fall"); score -= 4              # noqa: E702
    if sign == EXALTATION.get(planet) and "exaltation" not in layers:
        layers.append("exaltation"); score += 4        # noqa: E702
    day_lord, night_lord = TRIPLICITY[ELEMENT_OF[sign]]
    trip = (day_lord if day else night_lord) if day is not None else None
    if planet in ((trip,) if trip else (day_lord, night_lord)):
        layers.append("triplicity"); score += 3        # noqa: E702
    if term_ruler(sign, deg) == planet:
        layers.append("term"); score += 2              # noqa: E702
    if face_ruler(lon) == planet:
        layers.append("face"); score += 1              # noqa: E702
    positive = {"domicile", "exaltation", "triplicity", "term", "face"}
    peregrine = not (set(layers) & positive)
    return {"layers": layers, "score": score, "peregrine": peregrine,
            "term_lord": term_ruler(sign, deg), "face_lord": face_ruler(lon)}


def sign_relation(planet: str, sign: str) -> str:
    lord = TRADITIONAL_RULERS[sign]
    if lord == planet:
        return "own"
    if lord in NATURAL_FRIENDS[planet]:
        return "friend"
    if lord in NATURAL_ENEMIES[planet]:
        return "enemy"
    return "neutral"


@dataclass
class PlanetCards:
    system: str
    chart_ruler: str | None
    sect: str | None
    cards: list[dict] = field(default_factory=list)
    dispositors: dict = field(default_factory=dict)
    receptions: list[dict] = field(default_factory=list)
    keynotes: list[dict] = field(default_factory=list)
    themes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def planet_cards(chart: BirthChart, sect: str | None = None) -> PlanetCards:
    vedic = chart.system == "vedic"
    has_angles = chart.time_known and chart.ascendant is not None
    p = {x.name: x for x in chart.planets}
    sun = p["Sun"]
    day = None if sect is None else sect == "day"
    angles = [chart.ascendant.longitude, (chart.ascendant.longitude + 180) % 360] if has_angles else []
    if has_angles and chart.midheaven is not None:
        angles += [chart.midheaven.longitude, (chart.midheaven.longitude + 180) % 360]
    chart_ruler = TRADITIONAL_RULERS[chart.ascendant.sign] if has_angles else None

    cards = []
    for name in CLASSICAL:
        pl = p[name]
        comfort: dict
        if vedic:
            comfort = {"dignity": vedic_dignity(name, pl.longitude), "relation": sign_relation(name, pl.sign),
                       "vargottama": navamsa_sign(pl.longitude) == pl.sign}
        else:
            comfort = essential_layers(name, pl.longitude, day)
        ability = []
        if has_angles and pl.house:
            ability.append(["angular", "succedent", "cadent"][(pl.house - 1) % 3])
        if any(_sep(pl.longitude, a) <= 5 for a in angles):
            ability.append("on an angle")
        if pl.retrograde and name not in ("Sun", "Moon"):
            ability.append("retrograde")
        ability.append("fast" if abs(pl.speed) >= MEAN_SPEED[name] else "slow")
        if name != "Sun":
            d = _sep(pl.longitude, sun.longitude)
            if vedic:
                orb = (COMBUSTION_ORB_RETRO.get(name, COMBUSTION_ORB.get(name, 0)) if pl.retrograde else COMBUSTION_ORB.get(name, 0))
                if d <= orb:
                    ability.append("combust")
            elif d <= 17 / 60:
                ability.append("cazimi")
            elif d <= 8.5:
                ability.append("combust")
            elif d <= 17:
                ability.append("under the beams")
        team = None
        if not vedic and day is not None and name not in ("Mercury",):
            in_sect = (name in DIURNAL) == day
            team = "in sect" if in_sect else "out of sect"
            if name == ("Jupiter" if day else "Venus"):
                team = "benefic of sect"
            if name == ("Mars" if day else "Saturn"):
                team = "malefic contrary to sect"
        boss = TRADITIONAL_RULERS[pl.sign]
        cards.append({"planet": name, "sign": pl.sign, "degree": round(pl.sign_degree, 1), "house": pl.house if has_angles else None,
                      "comfort": comfort, "ability": ability, "team": team, "boss": boss if boss != name else None})

    # Dispositor chains: follow sign rulers until a planet in its own sign or a repeat.
    chains, finals, loops = {}, set(), []
    for name in CLASSICAL:
        chain, cur = [name], name
        while True:
            nxt = TRADITIONAL_RULERS[p[cur].sign]
            if nxt == cur:
                finals.add(cur)
                break
            if nxt in chain:
                loop = chain[chain.index(nxt):]
                key = sorted(loop)
                if key not in [sorted(x) for x in loops]:
                    loops.append(loop)
                break
            chain.append(nxt)
            cur = nxt
        chains[name] = chain
    final = next(iter(finals)) if len(finals) == 1 and not loops else None
    dispositors = {"chains": chains, "final": final, "self_ruled": sorted(finals), "loops": loops}

    receptions = []
    for i, a in enumerate(CLASSICAL):
        for b in CLASSICAL[i + 1:]:
            if TRADITIONAL_RULERS[p[a].sign] == b and TRADITIONAL_RULERS[p[b].sign] == a:
                receptions.append({"planets": [a, b], "kind": "mutual reception by sign"})

    # Keynotes: score chart factors and keep the top five (3.11).
    notes: list[tuple[int, str, str]] = [(10, "Sun", f"Sun in {sun.sign}"), (10, "Moon", f"Moon in {p['Moon'].sign}")]
    if has_angles:
        notes.append((10, "Ascendant", f"{chart.ascendant.sign} rising"))
        notes.append((8, chart_ruler, f"{chart_ruler} rules your chart, from {p[chart_ruler].sign}"))
    for c in cards:
        if "on an angle" in c["ability"]:
            notes.append((7, c["planet"], f"{c['planet']} sits right on an angle"))
        comfort = c["comfort"]
        score = comfort.get("score")
        if score is not None and abs(score) >= 5:
            notes.append((4, c["planet"], f"{c['planet']} is {'very strong' if score > 0 else 'challenged'} by sign"))
        if c["team"] == "malefic contrary to sect":
            notes.append((4, c["planet"], f"{c['planet']} is your steepest growth edge (contrary to sect)"))
    for a in chart.aspects:
        if a.orb < 1 and a.a in CLASSICAL and a.b in CLASSICAL:
            notes.append((6, a.a, f"{a.a} {a.kind} {a.b}, almost exact"))
    if final:
        notes.append((5, final, f"{final} is the final dispositor: everything reports to it"))
    seen, keynotes = set(), []
    for score, key, text in sorted(notes, key=lambda n: -n[0]):
        if text in seen:
            continue
        seen.add(text)
        keynotes.append({"score": score, "factor": key, "text": text})
        if len(keynotes) == 5:
            break

    # Themes: Herring's alphabet.
    tally = {n: 0.0 for n in range(1, 13)}
    if has_angles:
        tally[SIGNS.index(chart.ascendant.sign) + 1] += 3
    tally[SIGNS.index(sun.sign) + 1] += 2
    tally[SIGNS.index(p["Moon"].sign) + 1] += 2
    for x in chart.planets:
        if x.name in CLASSICAL + ["Uranus", "Neptune", "Pluto"]:
            tally[SIGNS.index(x.sign) + 1] += 1
            if has_angles and x.house:
                tally[x.house] += 1
    for n, planet in LETTER_PLANET.items():
        if planet in p and any(_sep(p[planet].longitude, a) <= 5 for a in angles):
            tally[n] += 2
    ranked = sorted(tally.items(), key=lambda kv: -kv[1])
    top = ranked[0][1]
    themes = [{"letter": n, "score": s, "sign": SIGNS[n - 1], "planet": LETTER_PLANET[n]} for n, s in ranked[:2] if s >= 0.75 * top]

    return PlanetCards(chart.system, chart_ruler, sect if not vedic else None, cards, dispositors, receptions, keynotes, themes)
