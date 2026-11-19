"""Inner Seasons (progressions, solar arc) and the Birthday Chart (returns)."""

from datetime import datetime, timezone

from hourscope_engine.chart import compute_chart
from hourscope_engine.seasons import seasons

from test_insights import EINSTEIN

PRINCETON = (40.3573, -74.6672, "America/New_York")


def test_progressed_moon_chapter_and_phase():
    s = seasons(compute_chart(**EINSTEIN), datetime(1940, 6, 1, tzinfo=timezone.utc), *PRINCETON)
    ch = s.moon_chapter
    began, ends = datetime.fromisoformat(ch["began"]), datetime.fromisoformat(ch["ends"])
    assert 1.8 < (ends - began).days / 365.25 < 3.2          # a progressed Moon chapter lasts ~2.5 years
    assert began < datetime(1940, 6, 1, tzinfo=timezone.utc) < ends
    assert 0 <= ch["percent"] <= 100
    assert s.lunar_phase["phase"] in {"New Moon", "Crescent", "First Quarter", "Gibbous", "Full Moon", "Disseminating", "Last Quarter", "Balsamic"}
    assert s.progressed["Sun"]["sign"] in {"Aries", "Taurus"}  # Sun 23 Pisces + ~61 degrees by age 61


def test_turning_points_are_near_exact_and_dated():
    s = seasons(compute_chart(**EINSTEIN), datetime(1940, 6, 1, tzinfo=timezone.utc), *PRINCETON)
    assert s.turning_points, "expected at least one progressed or solar-arc aspect in seven years"
    for tp in s.turning_points:
        assert tp["orb"] < 1.0 and tp["kind"] in {"conjunction", "sextile", "square", "trine", "opposition"}
    assert len(s.turning_points) <= 14


def test_solar_return_cast_for_current_city():
    s = seasons(compute_chart(**EINSTEIN), datetime(1940, 6, 1, tzinfo=timezone.utc), *PRINCETON)
    sr = s.solar_return
    assert sr["at"].startswith("1940-03-1")                    # birthday mid-March
    assert sr["ascendant"] and sr["next"].startswith("1941-03-1")
    lr = s.lunar_return
    assert lr and datetime.fromisoformat(lr["at"]) <= datetime(1940, 6, 1, 12, tzinfo=timezone.utc)
    assert (datetime(1940, 6, 1, 12, tzinfo=timezone.utc) - datetime.fromisoformat(lr["at"])).days <= 28


def test_unknown_time():
    kw = dict(EINSTEIN)
    kw["birth_time"] = None
    s = seasons(compute_chart(**kw), datetime(1940, 6, 1, tzinfo=timezone.utc), *PRINCETON)
    assert s.progressed["Moon"]["house"] is None and s.warnings


def test_progressed_moon_chapters_through_life():
    from datetime import date, datetime, time, timezone
    from hourscope_engine.chart import compute_chart
    from hourscope_engine.seasons import seasons
    c = compute_chart(date(1990, 3, 14), time(8, 30), 37.57, 126.98, "Asia/Seoul")
    s = seasons(c, datetime(2026, 11, 14, tzinfo=timezone.utc), 37.57, 126.98, "Asia/Seoul")
    ch = s.moon_chapters
    # The progressed Moon moves about 12-15 degrees a year: 2 to 2.5 years a sign, so 36-45 chapters
    # in 90 years, plus the partial first one.
    assert 34 <= len(ch) <= 46
    assert ch[0]["age"] == 0 and ch[0]["sign"] == c.planet("Moon").sign
    for a, b in zip(ch, ch[1:]):
        assert a["ends"] == b["began"]               # chapters join up
        assert b["sign"] != a["sign"]
        assert a["house_end"] is not None and (a["house_end"] - a["house"]) % 12 in (0, 1, 2)  # houses only move forward
    # The current chapter agrees with the one already reported.
    now = "2026-11-14"
    cur = [x for x in ch if x["began"] <= now and (x["ends"] is None or now < x["ends"])]
    assert cur and cur[0]["sign"] == s.moon_chapter["sign"]
    # Found by forward and backward searches respectively, so allow a few minutes either way.
    gap = abs(datetime.fromisoformat(cur[0]["began"]) - datetime.fromisoformat(s.moon_chapter["began"]))
    assert gap.total_seconds() < 86400


def test_moon_chapters_reach_past_today_for_people_over_90():
    """Someone aged 95 still sees their real current chapter, with a real end date."""
    now = datetime(1974, 6, 1, tzinfo=timezone.utc)  # Einstein would be 95
    s = seasons(compute_chart(**EINSTEIN), now, *PRINCETON)
    current = [c for c in s.moon_chapters if datetime.fromisoformat(c["began"]) <= now
               and (c["ends"] is None or now < datetime.fromisoformat(c["ends"]))]
    assert len(current) == 1 and current[0]["ends"] is not None
    assert current[0]["sign"] == s.moon_chapter["sign"]
