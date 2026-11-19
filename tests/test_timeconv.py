"""Local birth time -> UTC, using historical time zone rules (ground rule 3)."""

from datetime import date, datetime, time, timedelta, timezone

from hourscope_engine.timeconv import local_to_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_local_mean_time_uses_birthplace_longitude():
    # Einstein, Ulm 10e0, 1879: before German standard time (1893).
    # Astro-Databank: "LMT m10e0" -> 11:30 local = 10:50 UT.
    r = local_to_utc(date(1879, 3, 14), time(11, 30), "Europe/Berlin", 10.0)
    assert r.time_basis == "local_mean_time"
    assert r.utc == utc(1879, 3, 14, 10, 50)


def test_today_offset_is_not_assumed_korea_1988_daylight_saving():
    # South Korea used daylight saving (UTC+10) in summer 1988 only.
    r = local_to_utc(date(1988, 7, 1), time(12, 0), "Asia/Seoul", 126.98)
    assert r.utc_offset == timedelta(hours=10)
    assert r.utc == utc(1988, 7, 1, 2, 0)
    r = local_to_utc(date(2020, 7, 1), time(12, 0), "Asia/Seoul", 126.98)
    assert r.utc_offset == timedelta(hours=9)


def test_britain_kept_summer_time_through_winter_1940():
    r = local_to_utc(date(1940, 10, 9), time(18, 30), "Europe/London", -2.98)
    assert r.utc_offset == timedelta(hours=1)
    assert r.utc == utc(1940, 10, 9, 17, 30)


def test_hawaii_1961_no_daylight_saving():
    r = local_to_utc(date(1961, 8, 4), time(19, 24), "Pacific/Honolulu", -157.86)
    assert r.utc_offset == timedelta(hours=-10)
    assert r.utc == utc(1961, 8, 5, 5, 24)


def test_clock_time_that_never_existed_is_flagged():
    # New York, 14 Mar 2021: clocks jumped from 02:00 to 03:00.
    r = local_to_utc(date(2021, 3, 14), time(2, 30), "America/New_York", -74.0)
    assert any("did not exist" in w for w in r.warnings)


def test_clock_time_that_happened_twice_is_flagged():
    # New York, 7 Nov 2021: 01:00-02:00 happened twice.
    r = local_to_utc(date(2021, 11, 7), time(1, 30), "America/New_York", -74.0)
    assert any("happened twice" in w for w in r.warnings)
    assert r.utc == utc(2021, 11, 7, 5, 30)  # first occurrence (EDT)


def test_india_1889_uses_madras_time_like_astro_databank():
    # Nehru, Allahabad 1889: ADB uses "MMT m80e1730" (UTC+5:21:10).
    r = local_to_utc(date(1889, 11, 14), time(23, 30), "Asia/Kolkata", 81.85)
    assert r.abbreviation == "MMT"
    assert r.utc_offset == timedelta(hours=5, minutes=21, seconds=10)


def test_india_before_1956_warns_time_history_uncertain():
    r = local_to_utc(date(1917, 11, 19), time(23, 11), "Asia/Kolkata", 81.85)
    assert r.time_basis == "zone"
    assert any("uncertain" in w for w in r.warnings)


def test_manual_offset_overrides_database():
    r = local_to_utc(date(1950, 1, 1), time(12, 0), "Asia/Kolkata", 72.88, manual_utc_offset_hours=4.85)
    assert r.time_basis == "manual_offset"
    assert r.utc == utc(1950, 1, 1, 7, 9)


def test_india_wartime_clocks_are_applied_not_todays_offset():
    """India ran clocks at UTC+6:30 during the Second World War (IANA Asia/Kolkata):
    from October 1941, back to +5:30 from mid-May 1942, then +6:30 again from September 1942
    until mid-October 1945. A Bombay birth at 6:34 local shows the difference."""
    cases = {
        date(1941, 12, 1): (timedelta(hours=6, minutes=30), utc(1941, 12, 1, 0, 4)),
        date(1942, 7, 1): (timedelta(hours=5, minutes=30), utc(1942, 7, 1, 1, 4)),
        date(1944, 8, 20): (timedelta(hours=6, minutes=30), utc(1944, 8, 20, 0, 4)),
        date(1946, 1, 1): (timedelta(hours=5, minutes=30), utc(1946, 1, 1, 1, 4)),
    }
    for d, (offset, expected) in cases.items():
        r = local_to_utc(d, time(6, 34), "Asia/Kolkata", 72.88)
        assert r.utc_offset == offset, d
        assert r.utc == expected, d
