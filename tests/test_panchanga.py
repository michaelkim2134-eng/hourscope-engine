"""Panchanga and personal stars (see docs/research/vedic-timing.md)."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from hourscope_engine.chart import NAKSHATRA_SPAN, compute_chart
from hourscope_engine.daily import daily_report
from hourscope_engine.hours import planetary_day
from hourscope_engine.panchanga import chandra_bala, day_windows, karana_name, panchanga, tara_of

NYC = (40.7128, -74.0060, "America/New_York")


def test_eclipse_day_tithi_and_star():
    # Total solar eclipse, 8 April 2024: new Moon at about 18:21 UTC (14:21 EDT).
    pd = planetary_day(date(2024, 4, 8), *NYC)
    p = panchanga(pd)
    assert p.tithi.name == "Amavasya" and p.tithi.number == 30
    ends = datetime.fromisoformat(p.tithi.ends_at).astimezone(timezone.utc)
    assert abs(ends - datetime(2024, 4, 8, 18, 21, tzinfo=timezone.utc)) < timedelta(minutes=10)
    assert p.nakshatra.name == "Revati"
    assert p.tithi.note == "less ideal for new starts"
    assert p.vara.name == "Moon" and p.vara.note == "Somavara"
    # After Amavasya comes the first lunar day of the bright half.
    assert p.tithi.next == "Shukla Pratipada"


def test_karana_names():
    assert karana_name(0) == "Kimstughna"
    assert karana_name(1) == "Bava"
    assert karana_name(7) == "Vishti"
    assert karana_name(8) == "Bava"
    assert karana_name(56) == "Vishti"
    assert [karana_name(k) for k in (57, 58, 59)] == ["Shakuni", "Chatushpada", "Naga"]


def test_tara_and_chandra_bala():
    assert tara_of(0, 0) == (1, "Janma", "mixed")
    assert tara_of(0, 1) == (2, "Sampat", "good")
    assert tara_of(0, 6) == (7, "Naidhana", "rest")
    assert tara_of(5, 4) == (9, "Parama Mitra", "good")    # wraps round the 27 stars
    assert tara_of(0, 9) == (1, "Janma", "mixed")          # second round of nine
    assert chandra_bala("Aries", "Aries") == (1, "good")
    assert chandra_bala("Aries", "Scorpio") == (8, "rest")  # chandrashtama
    assert chandra_bala("Pisces", "Aries") == (2, "weak")


def test_day_windows_follow_the_weekday_parts():
    # Sunday 2024-04-07: Rahu Kaal part 8, Yamaganda part 5, Gulika part 7; Abhijit around noon.
    pd = planetary_day(date(2024, 4, 7), *NYC)
    w = day_windows(pd)
    eighth = (pd.sunset - pd.sunrise) / 8
    assert w["yamaganda"][0] == pd.sunrise + eighth * 4
    assert w["gulika"][0] == pd.sunrise + eighth * 6
    assert w["rahu_kaal"][0] == pd.sunrise + eighth * 7
    mid = pd.sunrise + (pd.sunset - pd.sunrise) / 2
    assert w["abhijit"][0] < mid < w["abhijit"][1]
    # No Abhijit on Wednesdays.
    assert day_windows(planetary_day(date(2024, 4, 10), *NYC))["abhijit"] is None


def test_limbs_change_within_the_day_or_not_at_all():
    pd = planetary_day(date(2024, 4, 7), *NYC)
    p = panchanga(pd)
    for limb in (p.tithi, p.nakshatra, p.yoga, p.karana):
        if limb.ends_at:
            t = datetime.fromisoformat(limb.ends_at)
            assert pd.sunrise < t < pd.next_sunrise
    assert p.karana.ends_at is not None     # a karana lasts about half a day


def test_daily_report_carries_panchanga_for_vedic_only():
    kw = dict(birth_date=date(1990, 6, 15), local_date=date(2024, 4, 7), latitude=NYC[0], longitude=NYC[1],
              timezone_name=NYC[2])
    vedic = compute_chart(date(1990, 6, 15), time(14, 30), 51.5074, -0.1278, "Europe/London", system="vedic")
    western = compute_chart(date(1990, 6, 15), time(14, 30), 51.5074, -0.1278, "Europe/London")
    rv = daily_report(vedic, **kw)
    assert rv.panchanga and rv.panchanga["personal"]["tara"]["name"]
    assert rv.panchanga["personal"]["uncertain"] is False
    assert any("Yamaganda" in " ".join(h.reasons) for h in rv.hours)
    assert daily_report(western, **kw).panchanga is None


def test_unknown_birth_time_flags_star_near_a_boundary():
    pd = planetary_day(date(2024, 4, 7), *NYC)
    near = NAKSHATRA_SPAN * 3 + 2.0     # 2 degrees into a star
    assert panchanga(pd, near, birth_time_known=False).personal["uncertain"] is True
    middle = NAKSHATRA_SPAN * 3 + 6.67
    assert panchanga(pd, middle, birth_time_known=False).personal["uncertain"] is False
