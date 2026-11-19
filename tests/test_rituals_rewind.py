"""New/full Moon finder (Moon Ritual Prompts) and the sky on past dates (Life Rewind)."""

from datetime import date, datetime, time

import swisseph as swe

from hourscope_engine import compute_chart
from hourscope_engine.lunar import lunations
from hourscope_engine.transits import sky_on

BIRTH = dict(birth_date=date(1990, 3, 14), birth_time=time(15, 20), latitude=37.566, longitude=126.978, timezone_name="Asia/Seoul")


def test_eclipse_new_moon_2024_is_found_to_the_minute():
    # The 8 April 2024 total solar eclipse new Moon was at 18:21 UTC (verified in test_charts.py).
    found = [l for l in lunations(swe.julday(2024, 4, 1, 0), swe.julday(2024, 4, 15, 0)) if l["type"] == "new"]
    assert len(found) == 1
    at = datetime.fromisoformat(found[0]["at"])
    assert (at.year, at.month, at.day, at.hour) == (2024, 4, 8, 18) and abs(at.minute - 21) <= 3
    assert found[0]["sign"] == "Aries"


def test_lunations_alternate_about_every_two_weeks():
    ls = lunations(swe.julday(2026, 1, 1, 0), swe.julday(2026, 12, 31, 0))
    assert 24 <= len(ls) <= 26
    for a, b in zip(ls, ls[1:]):
        assert a["type"] != b["type"]
        gap = (datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"])).total_seconds() / 86400
        assert 13.5 < gap < 16.2


def test_sky_on_a_past_date():
    r = sky_on(compute_chart(**BIRTH), BIRTH["birth_date"], date(2019, 6, 1))
    assert r["personal_year"] == 2  # 3 + 5 + (2019 -> 12 -> 3) = 11 -> 2
    assert r["transits"] and all(t["orb"] <= 3.0 for t in r["transits"])
    assert r["transits"] == sorted(r["transits"], key=lambda t: (-t["weight"], t["orb"]))
    assert "Saturn" in r["retrogrades"]  # Saturn was retrograde from late April to mid-September 2019
    assert r["moon_phase"] and r["moon_sign"]


def test_eclipses_near_a_date():
    r = sky_on(compute_chart(**BIRTH), BIRTH["birth_date"], date(2024, 4, 1))
    assert any(e["type"] == "solar" and e["at"].startswith("2024-04-08") for e in r["eclipses"])


def test_vedic_rewind_has_dasha():
    r = sky_on(compute_chart(**BIRTH, system="vedic"), BIRTH["birth_date"], date(2015, 1, 1))
    assert r["dasha"] and r["dasha"]["mahadasha"]
