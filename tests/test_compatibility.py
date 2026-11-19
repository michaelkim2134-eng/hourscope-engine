"""Compatibility Studio: koota tables and rules, Manglik, synastry, unknown-time range."""

from datetime import date, time

from hourscope_engine.chart import NAKSHATRA_SPAN, NAKSHATRAS, SIGNS
from hourscope_engine.compatibility import (
    MAX, VASHYA_MATRIX, YONI_ANIMALS, YONI_MATRIX, YONI_OF, ashtakoota, compatibility, nadi_of, vashya_group,
)

ENEMIES = [("Horse", "Buffalo"), ("Elephant", "Lion"), ("Sheep", "Monkey"), ("Serpent", "Mongoose"),
           ("Dog", "Deer"), ("Cat", "Rat"), ("Cow", "Tiger")]


def mid_of(nak: str) -> float:
    return NAKSHATRAS.index(nak) * NAKSHATRA_SPAN + NAKSHATRA_SPAN / 2


def test_tables_are_symmetric_and_enemies_score_zero():
    for m in (YONI_MATRIX, VASHYA_MATRIX):
        assert all(m[i][j] == m[j][i] for i in range(len(m)) for j in range(len(m)))
    for x, y in ENEMIES:
        assert YONI_MATRIX[YONI_ANIMALS.index(x)][YONI_ANIMALS.index(y)] == 0
    assert all(YONI_MATRIX[i][i] == 4 for i in range(14))
    assert set(YONI_OF) == set(NAKSHATRAS)


def test_nadi_shortcut_matches_classical_lists():
    adi = ["Ashwini", "Ardra", "Punarvasu", "Uttara Phalguni", "Hasta", "Jyeshtha", "Mula", "Shatabhisha", "Purva Bhadrapada"]
    assert all(nadi_of(NAKSHATRAS.index(n) + 1) == "adi" for n in adi)


def test_same_star_same_pada_scores_full_except_nadi():
    k = ashtakoota(mid_of("Rohini"), mid_of("Rohini"))
    assert k["parts"]["nadi"] == 0 and k["parts"]["yoni"] == 4 and k["parts"]["bhakoot"] == 7
    assert k["total"] <= 36 and all(k["parts"][p] <= MAX[p] for p in MAX)


def test_bhakoot_six_eight_and_band():
    # Moons in Aries and Virgo are 6/8 apart.
    k = ashtakoota(SIGNS.index("Aries") * 30 + 5, SIGNS.index("Virgo") * 30 + 5)
    assert k["parts"]["bhakoot"] == 0
    assert k["band"] in {"excellent", "good", "average", "effortful"}


def test_vashya_groups():
    assert vashya_group(SIGNS.index("Sagittarius") * 30 + 5) == "human"
    assert vashya_group(SIGNS.index("Sagittarius") * 30 + 20) == "quadruped"
    assert vashya_group(SIGNS.index("Capricorn") * 30 + 20) == "water"
    assert vashya_group(SIGNS.index("Leo") * 30) == "wild"


def test_full_comparison_and_unknown_time_range():
    a = dict(birth_date=date(1990, 6, 15), birth_time=time(14, 30), latitude=51.5074, longitude=-0.1278, timezone="Europe/London")
    b = dict(birth_date=date(1992, 2, 3), birth_time=None, latitude=40.7128, longitude=-74.006, timezone="America/New_York")
    c = compatibility(a, b)
    assert 0 <= c.ashtakoota["total"] <= 36
    assert c.range is not None and c.range["min"] <= c.range["max"]
    assert c.manglik["a"]["status"] in {"none", "cancelled", "present"}
    assert c.synastry and all(s["orb"] <= 6 for s in c.synastry)
    assert "Ascendant" not in c.composite          # one birth time unknown
    assert set(c.composite) >= {"Sun", "Moon", "Venus"}


def test_life_path_pairing():
    from hourscope_engine.compatibility import _numbers
    # 14 Mar 1879 -> Life Path 6; 29 Nov 1990 -> 1+1(11 kept)+2+9 ... reduce: 11 + 11 + 1 (1990->19->10->1) = 23 -> 5
    r = _numbers({"birth_date": date(1879, 3, 14)}, {"birth_date": date(1990, 11, 29)})
    assert r["a_life_path"] == 6 and r["b_life_path"] == 5
    assert r["pair"] == [5, 6] and r["same_family"] is False
    same = _numbers({"birth_date": date(1879, 3, 14)}, {"birth_date": date(1879, 3, 14)})
    assert same["pair"] == [6, 6] and same["same_family"] is True
