"""Public sky facts for social posts: cross-checked against the engine's own building blocks and fixed dates."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from hourscope_engine.api import app
from hourscope_engine.social import illumination, sky_day, universal_numbers

NYC = (40.7128, -74.006, "America/New_York")
client = TestClient(app)


def test_universal_numbers():
    # 2026 -> 10 -> 1; November (11 -> 2): 1 + 2 = 3; the 17th (8): 3 + 8 = 11 -> 2
    assert universal_numbers(date(2026, 11, 17)) == {"year": 1, "month": 3, "day": 2, "day_theme": "cooperation, patience and partnership"}
    assert universal_numbers(date(2027, 1, 1))["year"] == 2


def test_illumination():
    assert illumination(0) == pytest.approx(0)
    assert illumination(180) == pytest.approx(1)
    assert illumination(90) == pytest.approx(0.5)


def test_sky_day_shape_and_hours():
    s = sky_day(date(2026, 11, 17), *NYC, place="New York")
    assert s["weekday"] == "Tuesday" and s["day_ruler"] == "Mars"
    assert len(s["hours"]) == 24 and s["hours"][0]["ruler"] == "Mars"
    assert s["hours"][0]["start"] == s["sunrise"]
    assert len(s["planets"]) == 10
    assert 0 <= s["moon"]["illumination"] <= 100
    # First Quarter on Nov 17: waxing (elongation 90-135) and the lit share matches the angle.
    e = s["moon"]["elongation"]
    assert 90 <= e < 135
    assert s["moon"]["illumination"] == round(illumination(e) * 100)
    for v in s["moon"]["void_of_course"]:
        assert v["start"] < v["end"]


def test_moon_ingress_and_void_line_up():
    # Over two weeks, every day the Moon changes sign has a void period ending at that ingress.
    for d in range(1, 15):
        s = sky_day(date(2026, 12, d), *NYC)
        ing = s["moon"]["ingress"]
        if ing:
            assert any(v["end"] == ing["at"] for v in s["moon"]["void_of_course"])


def test_known_lunation_and_retrograde():
    # Full Moon of 2026-11-24 in Gemini; Mercury retrograde 2026-10-24 to 2026-11-13 (the retrograde module is
    # itself cross-checked against the French/Meeus model in test_retrogrades.py).
    s = sky_day(date(2026, 11, 1), *NYC)
    assert s["next_full_moon"]["sign"] == "Gemini" and s["next_full_moon"]["at"].startswith("2026-11-24")
    merc = next(r for r in s["retrogrades"] if r["planet"] == "Mercury")
    assert merc["station_retrograde"].startswith("2026-10-24") and merc["station_direct"].startswith("2026-11-13")
    assert any(st["planet"] == "Mercury" and st["type"] == "direct" for st in s["stations"])
    assert next(p for p in s["planets"] if p["name"] == "Mercury")["retrograde"] is True
    # Once Mercury is direct again it drops out of the list.
    later = sky_day(date(2026, 11, 17), *NYC)
    assert all(r["planet"] != "Mercury" for r in later["retrogrades"])


def test_planet_ingress_found_on_the_right_day():
    # Find a day in 2027 when the Sun changes sign and check the reported time sits inside that day.
    found = 0
    for m in range(1, 13):
        s = sky_day(date(2027, m, 20), *NYC)
        for i in s["ingresses"]:
            if i["planet"] == "Sun":
                at = datetime.fromisoformat(i["at"])
                assert at.date() == date(2027, m, 20)
                found += 1
    assert found >= 3


def test_endpoint():
    r = client.get("/v1/sky-day", params={"date": "2026-11-17", "lat": NYC[0], "lon": NYC[1], "tz": NYC[2], "place": "New York"})
    assert r.status_code == 200 and r.json()["place"] == "New York"
    assert client.get("/v1/sky-day", params={"date": "2026-11-17", "lat": 100, "lon": 0}).status_code == 422
