"""Sunrise/sunset, planetary hours and Rahu Kaal."""

import math
import random
from datetime import date, datetime, timedelta, timezone

import pymeeus.Coordinates as C
from pymeeus.Epoch import Epoch
from pymeeus.Sun import Sun

from hourscope_engine.hours import (
    CHALDEAN_ORDER, RAHU_KAAL_PART, WEEKDAY_RULERS, planetary_day, planetary_hour_at, ruler_sequence,
)
from hourscope_engine.places import timezone_at
from hourscope_engine.sky import datetime_from_jd, jd_from_datetime, next_sunrise, next_sunset


# ---------------------------------------------------------------- independent sunrise check
def sun_altitude(jd_ut: float, lat: float, lon: float) -> float:
    """Sun's altitude in degrees from the French VSOP87 model + Meeus formulas."""
    e = Epoch(jd_ut)  # UT vs TT (about a minute) moves the Sun by only ~2.5"
    slon, slat, _ = Sun.apparent_geocentric_position(e)
    ra, dec = C.ecliptical2equatorial(slon, slat, C.true_obliquity(e))
    t = (jd_ut - 2451545.0) / 36525
    gmst = (280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933 * t * t) % 360
    ha = math.radians((gmst + lon - ra()) % 360)
    phi, d = math.radians(lat), math.radians(dec())
    return math.degrees(math.asin(math.sin(phi) * math.sin(d) + math.cos(phi) * math.cos(d) * math.cos(ha)))


def independent_crossing(jd_guess: float, lat: float, lon: float) -> float:
    """Time near jd_guess when the Sun's centre is 50' below the horizon
    (34' refraction + 16' radius: the standard sunrise/sunset definition)."""
    target = -50 / 60
    lo, hi = jd_guess - 30 / 1440, jd_guess + 30 / 1440
    flo = sun_altitude(lo, lat, lon) - target
    for _ in range(50):
        mid = (lo + hi) / 2
        fm = sun_altitude(mid, lat, lon) - target
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def test_sunrise_and_sunset_match_french_models():
    rng = random.Random(42)
    worst = 0.0
    for _ in range(60):
        lat, lon = rng.uniform(-60, 60), rng.uniform(-180, 180)
        jd0 = 2447892.5 + rng.random() * 14600  # 1990-2030
        for finder in (next_sunrise, next_sunset):
            ours = finder(jd0, lat, lon)
            theirs = independent_crossing(ours, lat, lon)
            worst = max(worst, abs(ours - theirs) * 86400)
    # Refraction models differ slightly between sources; 1 minute is the
    # precision anyone reads a sunrise time to.
    assert worst <= 60, f"worst sunrise/sunset difference {worst:.0f} s"


# ---------------------------------------------------------------- planetary hours
NYC = (40.7128, -74.0060, "America/New_York")


def test_weekday_rulers_and_chaldean_order():
    assert WEEKDAY_RULERS[6] == "Sun" and WEEKDAY_RULERS[0] == "Moon" and WEEKDAY_RULERS[5] == "Saturn"
    assert CHALDEAN_ORDER == ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
    # Walking 24 hours through the Chaldean order always lands on the next
    # day's ruler: that's where the weekday order comes from.
    for i, ruler in enumerate(WEEKDAY_RULERS):
        assert ruler_sequence(ruler, 25)[24] == WEEKDAY_RULERS[(i + 1) % 7]


def test_planetary_day_structure():
    d = date(2026, 11, 10)  # a Tuesday
    pd = planetary_day(d, *NYC)
    assert pd.day_ruler == "Mars"
    assert len(pd.hours) == 24
    assert pd.hours[0].ruler == "Mars" and pd.hours[0].start == pd.sunrise
    assert pd.hours[11].end == pd.sunset and pd.hours[23].end == pd.next_sunrise
    for a, b in zip(pd.hours, pd.hours[1:]):
        assert a.end == b.start
    day_lengths = {round((h.end - h.start).total_seconds()) for h in pd.hours[:12]}
    night_lengths = {round((h.end - h.start).total_seconds()) for h in pd.hours[12:]}
    assert max(day_lengths) - min(day_lengths) <= 1
    assert max(night_lengths) - min(night_lengths) <= 1
    # November: short days, long nights
    assert max(day_lengths) < 3600 < min(night_lengths)
    assert [h.ruler for h in pd.hours] == ruler_sequence("Mars")


def test_before_sunrise_belongs_to_previous_planetary_day():
    pd = planetary_day(date(2026, 11, 10), *NYC)
    before = pd.sunrise - timedelta(minutes=5)
    h = planetary_hour_at(before, *NYC)
    assert h.number == 24  # last night hour of Monday's planetary day
    assert h.ruler == ruler_sequence("Moon")[23]
    after = pd.sunrise + timedelta(minutes=5)
    assert planetary_hour_at(after, *NYC).ruler == "Mars"


def test_clock_change_day_hours_stay_continuous():
    # New York, 8 March 2026: clocks jump forward at 2am.
    pd = planetary_day(date(2026, 3, 7), *NYC)
    total = pd.next_sunrise - pd.sunrise
    assert sum((h.end - h.start for h in pd.hours), timedelta()) == total
    assert pd.next_sunrise.utcoffset() == timedelta(hours=-4)
    assert pd.sunrise.utcoffset() == timedelta(hours=-5)


def test_sunrise_is_on_the_local_date_far_from_greenwich():
    for lat, lon in [(-33.87, 151.21), (21.31, -157.86), (35.68, 139.69)]:
        tz = timezone_at(lat, lon)
        pd = planetary_day(date(2026, 6, 1), lat, lon, tz)
        assert pd.sunrise.date() == date(2026, 6, 1)
        assert pd.sunrise < pd.sunset < pd.next_sunrise


def test_polar_day_and_night_fall_back_to_clock_hours():
    tromso = (69.65, 18.96, "Europe/Oslo")
    for d in (date(2026, 6, 21), date(2026, 12, 21)):
        pd = planetary_day(d, *tromso)
        assert pd.warnings and "polar" in pd.warnings[0]
        assert pd.sunrise.hour == 6 and pd.sunset.hour == 18
        assert len(pd.hours) == 24


def test_rahu_kaal_follows_the_weekday_rule():
    # With sunrise 6:00 and sunset 18:00 the classic table is:
    # Mon 7:30, Tue 15:00, Wed 12:00, Thu 13:30, Fri 10:30, Sat 9:00, Sun 16:30.
    classic_start_hours = [7.5, 15.0, 12.0, 13.5, 10.5, 9.0, 16.5]
    for wd, start in enumerate(classic_start_hours):
        assert 6 + (RAHU_KAAL_PART[wd] - 1) * 1.5 == start
    pd = planetary_day(date(2026, 11, 8), *NYC)  # Sunday: last eighth of daytime
    eighth = (pd.sunset - pd.sunrise) / 8
    assert pd.rahu_kaal == (pd.sunset - eighth, pd.sunset)


def test_julian_day_round_trip():
    dt = datetime(2026, 11, 10, 13, 45, 12, tzinfo=timezone.utc)
    assert datetime_from_jd(jd_from_datetime(dt)) == dt
