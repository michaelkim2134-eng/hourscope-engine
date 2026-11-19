"""Deeper chart facts and full numerology. Expected values are worked out by hand in the comments."""

from datetime import date, datetime, time, timezone

import pytest

from hourscope_engine import compute_chart
from hourscope_engine.chart import BirthChart, _position
from hourscope_engine.insights import (
    DASHA_YEARS, chart_insights, dignity, find_patterns, navamsa_sign, vimshottari,
)
from hourscope_engine.numerology import (
    expression_number, full_profile, personality_number, pinnacles_and_challenges, soul_urge_number,
)

EINSTEIN = dict(birth_date=date(1879, 3, 14), birth_time=time(11, 30), latitude=48.4, longitude=10.0,
                timezone_name="Europe/Berlin")


def fake_chart(longitudes: dict[str, float]) -> BirthChart:
    planets = [_position(n, lon, 1.0, vedic=False) for n, lon in longitudes.items()]
    return BirthChart(
        system="western", time_known=False, local_time="", utc_time="2000-01-01T00:00:00+00:00", timezone="UTC",
        time_basis="zone", latitude=0, longitude=0, zodiac="tropical", house_system=None, ayanamsa=None,
        planets=planets, ascendant=None, midheaven=None, house_cusps=None, aspects=[],
    )


# ---------------------------------------------------------------- Western facts
def test_dignities():
    assert dignity("Mars", "Capricorn") == "exaltation"
    assert dignity("Venus", "Aries") == "detriment"
    assert dignity("Saturn", "Aries") == "fall"
    assert dignity("Moon", "Cancer") == "domicile"
    assert dignity("Uranus", "Aquarius") is None


def test_einstein_insights():
    i = chart_insights(compute_chart(**EINSTEIN))
    # 10 bodies + Sun, Moon counted twice + Ascendant twice = 14 points
    assert sum(i.elements.values()) == 14 and sum(i.modalities.values()) == 14
    assert i.dignities == {"Venus": "detriment", "Mars": "exaltation", "Saturn": "fall"}
    assert i.sect == "day"  # Sun in the 10th house, above the horizon
    # Day-chart Part of Fortune = Ascendant + Moon - Sun = 2°39' Aries
    assert i.part_of_fortune["sign"] == "Aries" and int(i.part_of_fortune["degree"]) == 2
    assert any(p.kind == "stellium" and set(p.planets) == {"Mercury", "Venus", "Saturn"} for p in i.patterns)
    tenth = i.house_rulers[9]
    assert tenth["sign"] == "Pisces" and tenth["ruler"] == "Jupiter"


def test_grand_trine_t_square_and_grand_cross():
    gt = find_patterns(fake_chart({"Sun": 10, "Moon": 130, "Mars": 250, "Venus": 50}))
    assert any(p.kind == "grand trine" and set(p.planets) == {"Sun", "Moon", "Mars"} for p in gt)

    ts = find_patterns(fake_chart({"Sun": 10, "Moon": 190, "Mars": 100}))
    assert any(p.kind == "t-square" and p.planets[2] == "Mars" for p in ts)

    gc = find_patterns(fake_chart({"Sun": 10, "Moon": 190, "Mars": 100, "Venus": 280}))
    assert any(p.kind == "grand cross" for p in gc)
    assert not any(p.kind == "t-square" for p in gc)  # folded into the cross


# ---------------------------------------------------------------- Vedic facts
@pytest.mark.parametrize("lon, sign", [
    (0.0, "Aries"), (3.4, "Taurus"), (29.9, "Sagittarius"),  # Aries navamsas run Aries..Sagittarius
    (30.0, "Capricorn"),   # fixed signs start from the 9th: Taurus -> Capricorn
    (60.0, "Libra"),       # dual signs start from the 5th: Gemini -> Libra
    (90.0, "Cancer"),      # movable signs start from themselves
])
def test_navamsa(lon, sign):
    assert navamsa_sign(lon) == sign


def test_vimshottari_from_start_of_ashwini():
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    periods, current = vimshottari(0.0001, birth, now=datetime(2003, 6, 1, tzinfo=timezone.utc))
    assert [p.lord for p in periods] == ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    assert current["birth_dasha"] == "Ketu" and current["birth_balance_years"] == pytest.approx(7, abs=0.01)
    assert current["mahadasha"] == "Ketu"
    total_years = sum(DASHA_YEARS.values())
    assert total_years == 120
    start = date.fromisoformat(periods[0].start)
    end = date.fromisoformat(periods[-1].end)
    assert abs((end - start).days / 365.25 - 120) < 0.01
    # Antardashas fill each mahadasha exactly
    for p in periods:
        assert p.sub_periods[0].start == p.start
        assert p.sub_periods[0].lord == p.lord  # each period starts with its own sub-period
        gap = abs((date.fromisoformat(p.sub_periods[-1].end) - date.fromisoformat(p.end)).days)
        assert gap <= 1  # rounding to whole days


def test_vimshottari_balance_halfway_through_bharani():
    # Bharani (Venus, 20 years) runs 13°20'-26°40'; halfway = 20°, so 10 years remain.
    _, current = vimshottari(20.0, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert current["birth_dasha"] == "Venus" and current["birth_balance_years"] == pytest.approx(10, abs=0.01)


def test_einstein_vedic_insights():
    i = chart_insights(compute_chart(**EINSTEIN, system="vedic"))
    assert i.current_dasha["birth_dasha"] == "Mercury"  # Moon in Jyeshtha, ruled by Mercury
    names = {y.name for y in i.yogas}
    assert "Gajakesari" in names        # Jupiter 4th from the Moon
    assert "Budhaditya" in names        # Sun and Mercury together in Pisces
    assert "Malavya (Pancha Mahapurusha)" in names  # exalted Venus in the 10th from Gemini Lagna
    assert i.navamsa["Lagna"] in {"Pisces"}


# ---------------------------------------------------------------- numerology
def test_name_numbers_albert_einstein():
    # ALBERT = 1+3+2+5+9+2 = 22 (master, kept); EINSTEIN = 5+9+5+1+2+5+9+5 = 41 -> 5; 22+5 = 27 -> 9
    assert expression_number("Albert Einstein") == 9
    # vowels: A+E = 6; E+I+E+I = 28 -> 1; 6+1 = 7
    assert soul_urge_number("Albert Einstein") == 7
    # consonants: L+B+R+T = 16 -> 7; N+S+T+N = 13 -> 4; 7+4 = 11 (master)
    assert personality_number("Albert Einstein") == 11


def test_accents_and_case_are_ignored():
    assert expression_number("José María") == expression_number("JOSE MARIA")


def test_pinnacles_and_challenges_einstein():
    # m=3, d=14->5, y=1879->25->7; Life Path 6, so the first pinnacle ends at 36-6 = 30
    pc = pinnacles_and_challenges(date(1879, 3, 14))
    assert [p["number"] for p in pc["pinnacles"]] == [8, 3, 11, 1]
    assert [c["number"] for c in pc["challenges"]] == [2, 2, 0, 4]
    assert pc["pinnacles"][0]["to_age"] == 30 and pc["pinnacles"][3]["to_age"] is None


def test_full_profile():
    p = full_profile(date(1879, 3, 14), "Albert Einstein", date(2026, 11, 10))
    assert p["life_path"] == 6 and p["birthday"] == 5
    assert p["maturity"] == 6  # 6 + 9 = 15 -> 6
    assert 14 in p["karmic_debts"]  # born on the 14th
    assert {13, 16} <= set(p["karmic_debts"])  # from the name's compound totals
    no_name = full_profile(date(1879, 3, 14), None, date(2026, 11, 10))
    assert "expression" not in no_name and no_name["name_used"] is None
