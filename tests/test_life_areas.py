"""Life Areas: functional roles, house lords, Vedic aspects, exchanges."""

import pytest

from hourscope_engine.chart import SIGNS, compute_chart
from hourscope_engine.insights import TRADITIONAL_RULERS
from hourscope_engine.life_areas import functional_role, life_areas, vedic_aspects

from test_insights import EINSTEIN


def roles_for(lagna: str) -> dict[str, str]:
    signs = [SIGNS[(SIGNS.index(lagna) + i) % 12] for i in range(12)]
    out = {}
    for planet in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        ruled = {i + 1 for i, s in enumerate(signs) if TRADITIONAL_RULERS[s] == planet}
        out[planet] = functional_role(planet, ruled)
    return out


@pytest.mark.parametrize("lagna,yk", [("Taurus", "Saturn"), ("Libra", "Saturn"), ("Cancer", "Mars"), ("Leo", "Mars"),
                                       ("Capricorn", "Venus"), ("Aquarius", "Venus")])
def test_classic_yogakarakas(lagna, yk):
    roles = roles_for(lagna)
    assert roles[yk] == "yogakaraka"
    assert list(roles.values()).count("yogakaraka") == 1


def test_aries_cast_matches_the_textbook():
    r = roles_for("Aries")
    assert r["Mars"] == "ally"          # lagna lord (also rules the 8th)
    assert r["Sun"] == "ally"           # 5th lord
    assert r["Jupiter"] == "ally"       # 9th and 12th: the 12th takes the 9th's colour
    assert r["Mercury"] == "teacher"    # 3rd and 6th
    assert r["Saturn"] == "teacher"     # 10th and 11th


def test_vedic_aspects():
    assert vedic_aspects("Sun", "Aries") == ["Libra"]
    assert vedic_aspects("Mars", "Aries") == ["Libra", "Cancer", "Scorpio"]
    assert vedic_aspects("Jupiter", "Aries") == ["Libra", "Leo", "Sagittarius"]
    assert vedic_aspects("Saturn", "Aries") == ["Libra", "Gemini", "Capricorn"]


def test_einstein_life_areas():
    w = life_areas(compute_chart(**EINSTEIN))
    assert w.rising == "Cancer" and len(w.houses) == 12 and w.cast == []
    h1 = w.houses[0]
    assert h1["house"] == 1 and h1["lord"] == "Moon" and h1["class"] == ["kendra", "trikona"]
    v = life_areas(compute_chart(**EINSTEIN, system="vedic"))
    assert v.rising == "Gemini"
    assert [h["sign"] for h in v.houses][:3] == ["Gemini", "Cancer", "Leo"]   # whole sign
    assert any(h["aspected_by"] for h in v.houses)
    assert {c["role"] for c in v.cast} <= {"yogakaraka", "ally", "mixed", "neutral", "teacher"}
    assert v.cast[0]["role"] in ("yogakaraka", "ally")


def test_unknown_birth_time():
    kw = dict(EINSTEIN)
    kw["birth_time"] = None
    r = life_areas(compute_chart(**kw))
    assert r.houses == [] and r.warnings
