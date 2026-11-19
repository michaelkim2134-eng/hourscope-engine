"""Sky frames and big moments for the Living Wheel and Time Scrubber."""

from datetime import date, time

import pytest
import swisseph as swe

from hourscope_engine import compute_chart
from hourscope_engine.sky import longitude_of
from hourscope_engine.transits import sky_frames, transit_events

BIRTH = dict(birth_date=date(1990, 3, 14), birth_time=time(15, 20), latitude=37.566, longitude=126.978, timezone_name="Asia/Seoul")
JD = swe.julday(2026, 11, 13, 0)


def test_frames_match_the_engine_positions():
    frames = sky_frames(JD, 10)
    assert len(frames) == 11
    assert frames[0]["at"].startswith("2026-11-13T00:00")
    sun = next(p for p in frames[5]["planets"] if p["name"] == "Sun")
    assert abs(sun["lon"] - longitude_of("Sun", JD + 5)[0]) < 1e-3
    assert [p["name"] for p in frames[0]["planets"]][:3] == ["Sun", "Moon", "Mercury"]


@pytest.fixture(scope="module")
def western_events():
    return transit_events(compute_chart(**BIRTH), JD, 365)


def test_solar_return_is_on_the_birthday(western_events):
    sr = [e for e in western_events if e.kind == "return" and e.planets == ["Sun"]]
    assert len(sr) == 1 and sr[0].at.startswith("2027-03-1")  # 14 Mar local, give or take the time zone


def test_known_eclipses_and_stations(western_events):
    days = {e.at[:10] for e in western_events if e.kind == "eclipse"}
    assert "2027-02-06" in days            # annular solar eclipse
    assert "2027-02-20" in days            # lunar eclipse
    titles = {e.title for e in western_events}
    assert "Mars stations retrograde" in titles


def test_events_are_sorted_and_rated(western_events):
    assert [e.at for e in western_events] == sorted(e.at for e in western_events)
    assert all(1 <= e.importance <= 3 for e in western_events)
    assert any(e.kind == "transit" for e in western_events)


def test_transits_are_exact(western_events):
    natal = compute_chart(**BIRTH)
    for e in [e for e in western_events if e.kind == "transit" and e.planets[1] == "Sun"][:3]:
        planet, kind = e.planets[0], e.title.split()[1]
        angle = {"conjunction": 0, "square": 90, "trine": 120, "opposition": 180}[kind]
        from datetime import datetime
        dt = datetime.fromisoformat(e.at)
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + dt.second / 3600)
        sep = abs((longitude_of(planet, jd)[0] - natal.planet("Sun").longitude + 180) % 360 - 180)
        assert abs(sep - angle) < 0.01


def test_vedic_dasha_changes():
    ev = transit_events(compute_chart(**BIRTH, system="vedic"), JD, 365)
    assert any(e.kind == "dasha" for e in ev)
