"""Pythagorean numerology. Each expected value is worked out by hand in the comment."""

from datetime import date

from hourscope_engine.numerology import (
    life_path, personal_day, personal_month, personal_year, planet_for, reduce_number,
)


def test_reduce_number():
    assert reduce_number(1990) == 1             # 19 -> 10 -> 1
    assert reduce_number(29) == 2               # 11 -> 2
    assert reduce_number(29, keep_masters=True) == 11
    assert reduce_number(7) == 7


def test_life_path_examples():
    # 14 Mar 1990: 3 + (1+4=5) + (1990 -> 1) = 9
    assert life_path(date(1990, 3, 14)) == 9
    # 29 Nov 1985: 11 + 11 (masters kept) + (1985 -> 23 -> 5) = 27 -> 9
    assert life_path(date(1985, 11, 29)) == 9
    # 1 Jan 2025: 1 + 1 + (2025 -> 9) = 11, a master number, kept
    assert life_path(date(2025, 1, 1)) == 11
    # 9 Apr 2025: 4 + 9 + 9 = 22, kept
    assert life_path(date(2025, 4, 9)) == 22


def test_personal_cycles():
    birth = date(1990, 3, 14)
    # Personal Year 2026: 3 + 5 + (2026 -> 10 -> 1) = 9
    assert personal_year(birth, 2026) == 9
    # Personal Month Nov 2026: 9 + (11 -> 2) = 11 -> 2
    assert personal_month(birth, date(2026, 11, 10)) == 2
    # Personal Day 10 Nov 2026: 2 + (10 -> 1) = 3
    assert personal_day(birth, date(2026, 11, 10)) == 3


def test_number_planets():
    assert planet_for(1) == "Sun" and planet_for(9) == "Mars"
    assert planet_for(11) == "Moon" and planet_for(22) == "Uranus"


# ---- Deeper numbers (worked by hand)
from hourscope_engine.numerology import (
    age_on, current_period, full_profile, hidden_passions, karmic_lessons, letter_counts, life_cycles, life_path_pair,
)


def test_letter_counts_lessons_and_passions():
    # JOHN SMITH: J1 O6 H8 N5 S1 M4 I9 T2 H8
    counts = letter_counts("John Smith")
    assert counts == {1: 2, 2: 1, 3: 0, 4: 1, 5: 1, 6: 1, 7: 0, 8: 2, 9: 1}
    assert karmic_lessons("John Smith") == [3, 7]
    assert hidden_passions("John Smith") == [1, 8]  # tie: both shown
    assert karmic_lessons("Zoë-Ann") == karmic_lessons("ZOE ANN")  # accents and hyphens ignored


def test_life_cycles_follow_month_day_year():
    # 14 March 1879: Life Path 6, so the first cycle ends at 36 - 6 = 30.
    cycles = life_cycles(date(1879, 3, 14))
    assert [c["number"] for c in cycles] == [3, 5, 7]
    assert [(c["from_age"], c["to_age"]) for c in cycles] == [(0, 30), (31, 57), (58, None)]
    # Master numbers are kept: born 11 Nov -> 11, 11.
    assert [c["number"] for c in life_cycles(date(1990, 11, 29))][:2] == [11, 11]


def test_age_and_current_period():
    b = date(1879, 3, 14)
    assert age_on(b, date(1900, 3, 13)) == 20 and age_on(b, date(1900, 3, 14)) == 21
    cycles = life_cycles(b)
    assert current_period(cycles, 30)["cycle"] == 1
    assert current_period(cycles, 31)["cycle"] == 2
    assert current_period(cycles, 90)["cycle"] == 3


def test_life_path_pairs_reduce_masters_and_sort():
    assert life_path_pair(11, 4) == (2, 4)
    assert life_path_pair(33, 22) == (4, 6)
    assert life_path_pair(9, 1) == (1, 9)


def test_full_profile_includes_the_new_numbers():
    p = full_profile(date(1879, 3, 14), "Albert Einstein", date(1900, 6, 1))
    assert p["age"] == 21
    assert p["current"]["life_cycle"]["cycle"] == 1
    assert p["current"]["pinnacle"]["from_age"] == 0
    assert len(p["personal_year_ahead"]) == 9 and p["personal_year_ahead"][0]["year"] == 1900
    assert set(p["karmic_lessons"]).isdisjoint(n for n, k in letter_counts("Albert Einstein").items() if k)
    assert p["hidden_passions"]
    assert "karmic_lessons" not in full_profile(date(1879, 3, 14), None, date(1900, 6, 1))
