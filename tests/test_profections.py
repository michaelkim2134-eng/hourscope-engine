"""Annual and monthly profections (Your Year)."""

from datetime import date, datetime, timezone

from hourscope_engine.chart import compute_chart
from hourscope_engine.profections import profection

from test_insights import EINSTEIN   # Cancer rising, Sun 23 Pisces (14 March 1879, Ulm)


def at(y, m, d):
    return datetime(y, m, d, 12, tzinfo=timezone.utc)


def test_age_26_activates_the_3rd_house():
    p = profection(compute_chart(**EINSTEIN), at(1905, 6, 30))
    assert p.basis == "ascendant"
    assert (p.age, p.house, p.sign, p.lord) == (26, 3, "Virgo", "Mercury")
    assert p.starts.startswith("1905-03-1") and p.ends.startswith("1906-03-1")
    # 30 June is the 4th month after the return (Sun about 105 degrees past its natal place).
    assert (p.month.index, p.month.sign, p.month.house, p.month.lord) == (3, "Sagittarius", 6, "Jupiter")
    assert p.table[26] == {"age": 26, "sign": "Virgo", "house": 3, "lord": "Mercury"}
    assert p.table[12]["sign"] == "Cancer" and len(p.table) == 101


def test_the_year_turns_at_the_solar_return_not_before():
    c = compute_chart(**EINSTEIN)
    assert profection(c, at(1905, 3, 12)).age == 25
    assert profection(c, at(1905, 3, 16)).age == 26


def test_first_year_from_birth():
    p = profection(compute_chart(**EINSTEIN), at(1879, 9, 1))
    assert (p.age, p.house, p.sign, p.lord) == (0, 1, "Cancer", "Moon")
    assert p.natal_planets_in_sign == [] or all(isinstance(x, str) for x in p.natal_planets_in_sign)


def test_unknown_birth_time_counts_from_the_sun_sign():
    kw = dict(EINSTEIN)
    kw["birth_time"] = None
    p = profection(compute_chart(**kw), at(1905, 6, 30))
    assert p.basis == "sun"
    assert (p.sign, p.lord) == ("Taurus", "Venus")
    assert p.lord_natal["house"] is None


def test_all_twelve_months_are_returned_in_order():
    from datetime import date, datetime, time, timezone
    from hourscope_engine.chart import compute_chart
    from hourscope_engine.profections import profection
    c = compute_chart(date(1990, 3, 14), time(8, 30), 37.57, 126.98, "Asia/Seoul")
    p = profection(c, datetime(2026, 11, 14, tzinfo=timezone.utc))
    assert len(p.months) == 12
    assert p.months[0]["starts"] == p.starts and p.months[-1]["ends"] == p.ends
    for a, b in zip(p.months, p.months[1:]):
        assert a["ends"] == b["starts"] and a["starts"] < a["ends"]
    assert p.months[p.month.index] == {"index": p.month.index, "sign": p.month.sign, "house": p.month.house,
                                       "lord": p.month.lord, "starts": p.month.starts, "ends": p.month.ends}
    assert p.months[0]["sign"] == p.sign and p.months[0]["lord"] == p.lord
