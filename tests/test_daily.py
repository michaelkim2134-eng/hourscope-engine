"""Daily rating, theme and best hours."""

from datetime import date, datetime, time

import pytest

from hourscope_engine import compute_chart
from hourscope_engine.daily import SCORING, daily_report, dignity, score_hour
from hourscope_engine.numerology import Numerology
from hourscope_engine.sky import jd_from_datetime

BIRTH = date(1990, 3, 14)
NYC = (40.7128, -74.0060)
DAY = date(2026, 11, 10)


@pytest.fixture(scope="module")
def western():
    c = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")
    return daily_report(c, BIRTH, DAY, *NYC)


@pytest.fixture(scope="module")
def vedic():
    c = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul", system="vedic")
    return daily_report(c, BIRTH, DAY, *NYC)


def test_dignities():
    assert dignity("Sun", "Leo") == "domicile"
    assert dignity("Sun", "Aquarius") == "detriment"
    assert dignity("Venus", "Pisces") == "exaltation"
    assert dignity("Saturn", "Aries") == "fall"
    assert dignity("Mercury", "Virgo") == "domicile"
    assert dignity("Jupiter", "Leo") is None


@pytest.mark.parametrize("name", ["western", "vedic"])
def test_report_shape(name, request):
    r = request.getfixturevalue(name)
    assert r.timezone == "America/New_York"
    assert len(r.hours) == 24
    assert 1 <= r.rating <= 10
    assert all(0 <= h.score <= 100 for h in r.hours)
    assert 1 <= len(r.best_hours) <= SCORING["best_count"]
    assert r.best_hours == sorted(r.best_hours, key=lambda h: h.start)
    for h in r.best_hours:
        mid = datetime.fromisoformat(h.start) + (datetime.fromisoformat(h.end) - datetime.fromisoformat(h.start)) / 2
        assert SCORING["waking_start"] <= mid.time() < SCORING["waking_end"]
        assert h.reasons and h.good_for
    def mid(h):
        a, b = datetime.fromisoformat(h.start), datetime.fromisoformat(h.end)
        return (a + (b - a) / 2).time()
    awake = [h for h in r.hours if SCORING["waking_start"] <= mid(h) < SCORING["waking_end"]]
    others = [h.score for h in awake if h not in r.best_hours]
    assert min(h.score for h in r.best_hours) >= max(others, default=0)
    assert r.theme["personal_day_theme"]
    assert r.numerology["personal_day"] == 3


def test_western_has_void_of_course_and_vedic_has_rahu_kaal(western, vedic):
    assert western.moon["void_start"] and western.rahu_kaal is None
    assert vedic.rahu_kaal and vedic.theme["tithi"] and vedic.theme["moon_nakshatra"]


def test_rahu_kaal_penalty_applied(vedic):
    start, end = (datetime.fromisoformat(x) for x in vedic.rahu_kaal)
    for h in vedic.hours:
        h_start, h_end = datetime.fromisoformat(h.start), datetime.fromisoformat(h.end)
        overlaps = min(h_end, end) > max(h_start, start)
        flagged = any("Rahu Kaal" in r for r in h.reasons)
        assert flagged == overlaps, (h.start, h.reasons)


def test_scores_are_personal():
    other = compute_chart(date(1972, 8, 2), time(6, 5), 51.5, -0.12, "Europe/London")
    mine = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")
    a = daily_report(mine, BIRTH, DAY, *NYC)
    b = daily_report(other, date(1972, 8, 2), DAY, *NYC)
    assert [h.score for h in a.hours] != [h.score for h in b.hours]


def test_same_inputs_same_answer(western):
    c = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")
    again = daily_report(c, BIRTH, DAY, *NYC)
    assert again.to_dict() == western.to_dict()


def test_unknown_birth_time_still_works():
    c = compute_chart(BIRTH, None, 37.566, 126.978, "Asia/Seoul")
    r = daily_report(c, BIRTH, DAY, *NYC)
    assert any("Birth time unknown" in w for w in r.warnings)
    assert not any("Ascendant" in reason for h in r.hours for reason in h.reasons)


def test_polar_location_still_works():
    c = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")
    r = daily_report(c, BIRTH, date(2026, 12, 21), 69.65, 18.96)
    assert any("polar" in w for w in r.warnings) and len(r.hours) == 24


def test_void_of_course_penalty():
    c = compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")
    n = Numerology.for_day(BIRTH, DAY)
    jd = jd_from_datetime(datetime(2026, 11, 10, 15, 0).astimezone())
    plain, _ = score_hour("Jupiter", jd, c, n, None)
    void, reasons = score_hour("Jupiter", jd, c, n, (jd - 0.1, jd + 0.1))
    assert void == plain + SCORING["void_of_course_moon"] and "the Moon is void of course" in reasons


def test_sky_lists_todays_planets(western, vedic):
    names = [p["planet"] for p in western.sky]
    assert names == ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
    w_sun = western.sky[0]["sign"]
    v_sun = vedic.sky[0]["sign"]
    assert w_sun == "Scorpio" and v_sun == "Libra"  # 10 Nov 2026: tropical Scorpio, sidereal Libra
    assert all(0 <= p["degree"] < 30 for p in western.sky)
