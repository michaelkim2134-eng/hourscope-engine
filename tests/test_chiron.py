"""Chiron (rule 2: accuracy first).

PyMeeus has no Chiron, so the check is against sign changes printed in astrological
ephemerides and almanacs, which are timed to the day. We find each crossing ourselves by
bisection and require it within a day of the printed date.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
import swisseph as swe

from hourscope_engine import chart as chart_mod
from hourscope_engine.chart import chart_at_utc, chiron_available, compute_chart

pytestmark = pytest.mark.skipif(not chiron_available(), reason="seas_18.se1 not found (services/engine/ephe)")


def chiron_lon(moment: datetime) -> float:
    u = moment.astimezone(timezone.utc)
    jd = swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60, swe.GREG_CAL)
    p = chart_mod._chiron(jd)
    assert p is not None
    return p.longitude


def crossing(boundary: float, start: date, end: date) -> date:
    """The date Chiron crosses `boundary` degrees between start and end (either direction)."""
    def side(d: datetime) -> bool:
        return ((chiron_lon(d) - boundary + 180) % 360) - 180 >= 0

    lo = datetime.combine(start, time(0), timezone.utc)
    hi = datetime.combine(end, time(0), timezone.utc)
    assert side(lo) != side(hi), "no crossing in this window"
    while hi - lo > timedelta(hours=1):
        mid = lo + (hi - lo) / 2
        if side(mid) == side(lo):
            lo = mid
        else:
            hi = mid
    return hi.date()


# (boundary in degrees, search window, published date)
INGRESSES = [
    (0.0, date(2018, 4, 1), date(2018, 5, 1), date(2018, 4, 17)),     # enters Aries
    (0.0, date(2018, 9, 10), date(2018, 10, 10), date(2018, 9, 25)),  # back into Pisces (retrograde)
    (0.0, date(2019, 2, 1), date(2019, 3, 1), date(2019, 2, 18)),     # Aries for good
    (330.0, date(2010, 4, 1), date(2010, 5, 10), date(2010, 4, 20)),  # enters Pisces
    (330.0, date(2011, 1, 20), date(2011, 2, 25), date(2011, 2, 8)),  # Pisces for good
]


@pytest.mark.parametrize("boundary,start,end,published", INGRESSES)
def test_sign_changes_match_published_ephemerides(boundary, start, end, published):
    assert abs((crossing(boundary, start, end) - published).days) <= 1


def test_known_position_and_retrograde():
    # 1 Jan 2000, 0h UT: Chiron at about 11°34' Sagittarius, moving forward.
    p = chart_mod._chiron(swe.julday(2000, 1, 1, 0.0))
    assert p.sign == "Sagittarius" and abs(p.sign_degree - 11.56) < 0.05 and not p.retrograde
    # Mid-November 2026 Chiron is retrograde in late Aries.
    q = chart_mod._chiron(swe.julday(2026, 11, 14, 0.0))
    assert q.sign == "Aries" and q.retrograde


def test_western_chart_has_chiron_with_house_and_aspects():
    c = compute_chart(date(1879, 3, 14), time(11, 30), 48.4011, 9.9876, "Europe/Berlin")
    (chiron,) = c.points
    assert chiron.name == "Chiron" and chiron.sign == "Taurus" and chiron.house is not None
    assert all(a.a == "Chiron" and a.orb <= chart_mod.CHIRON_ORB for a in c.point_aspects)
    # Chiron stays out of `planets`, which the rest of the engine relies on.
    assert "Chiron" not in [p.name for p in c.planets]


def test_vedic_and_unknown_time():
    assert compute_chart(date(1879, 3, 14), time(11, 30), 48.4011, 9.9876, "Europe/Berlin", system="vedic").points == []
    c = compute_chart(date(1990, 3, 14), None, 37.57, 126.98, "Asia/Seoul")
    assert c.points[0].house is None  # rule 4: no houses without a birth time
    assert not any(a.b in ("Ascendant", "Midheaven") for a in c.point_aspects)


def test_relocated_charts_carry_chiron_too():
    c = chart_at_utc(datetime(2000, 6, 1, 12, tzinfo=timezone.utc), 51.5, -0.12)
    assert c.points and c.points[0].name == "Chiron"


def test_chiron_moments_in_big_dates():
    from hourscope_engine.sky import jd_from_datetime
    from hourscope_engine.transits import transit_events
    c = compute_chart(date(1879, 3, 14), time(11, 30), 48.4011, 9.9876, "Europe/Berlin")
    ev = transit_events(c, jd_from_datetime(datetime(1925, 1, 1, tzinfo=timezone.utc)), 365 * 6)
    returns = [e for e in ev if e.title == "Chiron return"]
    # Chiron takes about 50 years to come back: Einstein's falls at ages 48 to 50.
    assert returns and all("1927" <= e.at[:4] <= "1929" for e in returns)
    assert all(e.importance == 3 and e.planets == ["Chiron"] for e in returns)
    hits = [e for e in ev if e.title.endswith("your Chiron")]
    assert hits and all(e.kind == "transit" and e.planets[1] == "Chiron" for e in hits)
    # Vedic charts carry no Chiron, so no Chiron moments.
    v = compute_chart(date(1879, 3, 14), time(11, 30), 48.4011, 9.9876, "Europe/Berlin", system="vedic")
    assert not [e for e in transit_events(v, jd_from_datetime(datetime(1925, 1, 1, tzinfo=timezone.utc)), 365 * 6) if "Chiron" in e.title]
