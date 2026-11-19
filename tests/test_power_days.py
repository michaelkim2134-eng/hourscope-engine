"""Power Day Finder: ranked windows for an activity."""

from datetime import date, datetime, time

import pytest

from hourscope_engine import compute_chart
from hourscope_engine.electional import ACTIVITIES, find_power_windows

BIRTH = date(1990, 3, 14)
PHX = (33.45, -112.07, "America/Phoenix")


@pytest.fixture(scope="module")
def chart():
    return compute_chart(BIRTH, time(15, 20), 37.566, 126.978, "Asia/Seoul")


def test_rejects_unknown_activity_and_long_ranges(chart):
    with pytest.raises(ValueError):
        find_power_windows(chart, BIRTH, "skydive", date(2026, 11, 1), 7, *PHX)
    with pytest.raises(ValueError):
        find_power_windows(chart, BIRTH, "sign", date(2026, 11, 1), 400, *PHX)


def test_windows_are_ranked_varied_and_in_waking_hours(chart):
    ws = find_power_windows(chart, BIRTH, "ask", date(2026, 11, 1), 21, *PHX, top=10)
    assert 1 <= len(ws) <= 10
    assert [w.score for w in ws] == sorted((w.score for w in ws), reverse=True)
    per_day = {}
    for w in ws:
        per_day[w.date] = per_day.get(w.date, 0) + 1
        mid = datetime.fromisoformat(w.start) + (datetime.fromisoformat(w.end) - datetime.fromisoformat(w.start)) / 2
        assert 7 <= mid.hour < 22 and mid.date().isoformat() == w.date
        assert w.reasons and 0 <= w.score <= 100
    assert max(per_day.values()) <= 2


def test_activities_favour_their_planets(chart):
    for act in ("love", "sign", "launch"):
        ws = find_power_windows(chart, BIRTH, act, date(2026, 11, 1), 30, *PHX, top=5)
        a = ACTIVITIES[act]
        good = set(a.primary) | set(a.supporting)
        assert sum(w.ruler in good for w in ws) >= 4, (act, [w.ruler for w in ws])


def test_mercury_retrograde_counts_against_signing(chart):
    # Mercury was retrograde until about 12 Nov 2026 and direct afterwards.
    retro = find_power_windows(chart, BIRTH, "sign", date(2026, 11, 3), 7, *PHX, top=30)
    direct = find_power_windows(chart, BIRTH, "sign", date(2026, 11, 15), 7, *PHX, top=30)
    assert all(any("Mercury is retrograde" in r for r in w.reasons) for w in retro)
    assert not any("Mercury is retrograde" in r for w in direct for r in w.reasons)
    assert max(w.score for w in direct) > max(w.score for w in retro)


def test_windows_explain_themselves_with_checks():
    import time as _time
    from datetime import date, time as dtime

    from hourscope_engine.chart import compute_chart
    from hourscope_engine.electional import find_power_windows

    natal = compute_chart(date(1990, 6, 15), dtime(14, 30), 51.5074, -0.1278, "Europe/London", "vedic")
    t0 = _time.perf_counter()
    wins = find_power_windows(natal, date(1990, 6, 15), "sign", date(2026, 11, 14), 30, 40.7128, -74.006, "America/New_York")
    took = _time.perf_counter() - t0
    assert wins and took < 60
    for w in wins:
        assert w.checks and all({"label", "ok", "points"} <= set(c) for c in w.checks)
        assert 0 <= w.score <= 100
    labels = " ".join(c["label"] for w in wins for c in w.checks)
    assert "rising" in labels                    # refined with a chart for the moment
    assert "tara" in labels or "from your Moon" in labels   # Vedic personal stars
