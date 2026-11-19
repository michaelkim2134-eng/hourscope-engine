"""Retrograde periods: stations checked against the French/Meeus model, shadows by definition."""

from datetime import datetime

import pytest
import swisseph as swe
from pymeeus.Epoch import Epoch
from pymeeus.Mars import Mars
from pymeeus.Mercury import Mercury
from pymeeus.Venus import Venus

from hourscope_engine.retrogrades import retrogrades_between
from hourscope_engine.sky import jd_from_datetime, longitude_of

MEEUS = {"Mercury": Mercury, "Venus": Venus, "Mars": Mars}


def jd(iso: str) -> float:
    return jd_from_datetime(datetime.fromisoformat(iso))


@pytest.fixture(scope="module")
def periods():
    return retrogrades_between(swe.julday(2015, 1, 1, 0), swe.julday(2030, 12, 31, 0), planets=("Mercury", "Venus", "Mars"))


@pytest.mark.parametrize("planet", ["Mercury", "Venus", "Mars"])
def test_stations_match_meeus(periods, planet):
    # Meeus's station formulas are series approximations (good to about a day).
    ours = [p for p in periods if p.planet == planet]
    assert ours, planet
    for p in ours:
        sr = jd(p.station_retrograde)
        sd = jd(p.station_direct)
        m_sr = MEEUS[planet].station_longitude_1(Epoch(sr)).jde()
        m_sd = MEEUS[planet].station_longitude_2(Epoch(sd)).jde()
        assert abs(sr - m_sr) < 1.5, (planet, p.station_retrograde)
        assert abs(sd - m_sd) < 1.5, (planet, p.station_direct)


def test_mercury_2026(periods):
    starts = [p.station_retrograde[:10] for p in periods if p.planet == "Mercury" and p.station_retrograde.startswith("2026")]
    assert starts == ["2026-02-26", "2026-06-29", "2026-10-24"]


def test_shadow_dates_by_definition(periods):
    for p in periods[:12]:
        pre, sr, sd, post = (jd(x) for x in (p.pre_shadow_start, p.station_retrograde, p.station_direct, p.post_shadow_end))
        assert pre <= sr < sd <= post
        # Pre-shadow starts where the planet will later station direct...
        assert abs(((longitude_of(p.planet, pre)[0] - p.direct_longitude + 180) % 360) - 180) < 0.01
        # ...and the post-shadow ends back where it stationed retrograde.
        assert abs(((longitude_of(p.planet, post)[0] - p.retrograde_longitude + 180) % 360) - 180) < 0.01
        # Planet is actually moving backwards in the middle of the period.
        assert longitude_of(p.planet, (sr + sd) / 2)[1] < 0


def test_periods_running_past_the_range_are_found():
    rs = retrogrades_between(swe.julday(2026, 11, 1, 0), swe.julday(2026, 12, 31, 0), planets=("Jupiter",))
    assert any(r.station_retrograde.startswith("2026-12") for r in rs)
