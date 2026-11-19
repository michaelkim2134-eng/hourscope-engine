"""Independent cross-check against the French planetary models.

Our engine uses the Swiss Ephemeris. Here we recompute positions with a
completely separate source: the VSOP87 planetary theory (Bureau des
Longitudes, Paris) and the ELP2000 lunar theory (Paris Observatory), as
published in Jean Meeus's "Astronomical Algorithms" and implemented by the
PyMeeus library. If either model were wrong, these tests would fail.

We compare at hundreds of random moments between 1910 and 2030 (the birth
years of living users plus the near future for transits). Positions are
compared in Terrestrial Time so the only thing being tested is the
planetary models themselves.

Tolerances are far tighter than a chart needs (charts are read to the
arcminute; most bodies here agree to a few arcseconds).
"""

from __future__ import annotations

import math
import random
from datetime import date, time

import pytest
import swisseph as swe
import pymeeus.Coordinates as C
from pymeeus.Angle import Angle
from pymeeus.Epoch import JDE2000, Epoch
from pymeeus.Jupiter import Jupiter
from pymeeus.Mars import Mars
from pymeeus.Mercury import Mercury
from pymeeus.Moon import Moon
from pymeeus.Neptune import Neptune
from pymeeus.Pluto import Pluto
from pymeeus.Saturn import Saturn
from pymeeus.Sun import Sun
from pymeeus.Uranus import Uranus
from pymeeus.Venus import Venus

from hourscope_engine import compute_chart

ARCSEC = 1 / 3600
START_JD = 2418672.5   # 1910-01-01
END_JD = 2462867.5     # 2031-01-01

# Worst-case allowed difference, in arcseconds.
TOLERANCE = {
    "Sun": 5, "Mercury": 5, "Venus": 5, "Mars": 5, "Jupiter": 5, "Saturn": 5,
    "Uranus": 10, "Neptune": 10,
    "Moon": 30,        # Meeus's ELP2000 is a shortened series (~10" accuracy)
    "Pluto": 60,       # Meeus's Pluto is a fitted series, then precessed from J2000
    "North Node": 60,  # mean node formulas differ slightly between sources
}

_SWE_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
    "North Node": swe.MEAN_NODE,
}
_MEEUS_PLANETS = {
    "Mercury": Mercury, "Venus": Venus, "Mars": Mars, "Jupiter": Jupiter,
    "Saturn": Saturn, "Uranus": Uranus, "Neptune": Neptune,
}


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def random_jds(n: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [START_JD + rng.random() * (END_JD - START_JD) for _ in range(n)]


def meeus_longitude(body: str, jde: float) -> float:
    """Apparent ecliptic longitude (true equinox of date) from the French models."""
    e = Epoch(jde)
    if body == "Sun":
        return Sun.apparent_geocentric_position(e)[0].to_positive()()
    if body == "Moon":
        return Moon.apparent_ecliptical_pos(e)[0].to_positive()()
    if body == "North Node":
        return Moon.longitude_mean_ascending_node(e).to_positive()()
    if body == "Pluto":
        # Meeus gives Pluto's astrometric position on the J2000 sky; move it
        # to the equinox of date (precession) and add nutation.
        ra, dec = Pluto.geocentric_position(e)[:2]
        lon, lat = C.equatorial2ecliptical(ra, dec, C.mean_obliquity(Epoch(JDE2000)))
        lon, lat = C.precession_ecliptical(Epoch(JDE2000), e, lon, lat)
        return (lon + C.nutation_longitude(e)).to_positive()()
    ra, dec, _ = _MEEUS_PLANETS[body].geocentric_position(e)
    lon, _ = C.equatorial2ecliptical(ra, dec, C.true_obliquity(e))
    return lon.to_positive()()


@pytest.mark.parametrize("body", list(TOLERANCE))
def test_positions_match_french_models(body):
    flag = swe.FLG_MOSEPH
    worst = 0.0
    for jde in random_jds(500, seed=len(body) * 7919):
        ours = swe.calc(jde, _SWE_IDS[body], flag)[0][0]
        theirs = meeus_longitude(body, jde)
        worst = max(worst, angle_diff(ours, theirs) / ARCSEC)
    assert worst <= TOLERANCE[body], f'{body}: worst difference {worst:.1f}"'


# ---------------------------------------------------------------- angles
def sidereal_time_deg(jd_ut: float) -> float:
    """Apparent Greenwich sidereal time (Meeus, chapter 12), in degrees."""
    t = (jd_ut - 2451545.0) / 36525
    mean = (280.46061837 + 360.98564736629 * (jd_ut - 2451545.0)
            + 0.000387933 * t * t - t ** 3 / 38710000)
    e = Epoch(jd_ut)
    eq_of_equinoxes = C.nutation_longitude(e)() * math.cos(math.radians(C.true_obliquity(e)()))
    return (mean + eq_of_equinoxes) % 360


def asc_mc(jd_ut: float, lat: float, lon: float) -> tuple[float, float]:
    """Ascendant and Midheaven from the classic spherical-astronomy formulas."""
    ramc = math.radians((sidereal_time_deg(jd_ut) + lon) % 360)
    eps = math.radians(C.true_obliquity(Epoch(jd_ut))())
    phi = math.radians(lat)
    mc = math.degrees(math.atan2(math.sin(ramc), math.cos(ramc) * math.cos(eps))) % 360
    asc = math.degrees(math.atan2(
        math.cos(ramc),
        -(math.sin(ramc) * math.cos(eps) + math.tan(phi) * math.sin(eps)),
    )) % 360
    return asc, mc


def test_ascendant_and_midheaven_match_classic_formulas():
    rng = random.Random(2026)
    worst_asc = worst_mc = 0.0
    for jd in random_jds(1000, seed=99):
        lat = rng.uniform(-60, 60)   # where nearly everyone is born
        lon = rng.uniform(-180, 180)
        _, ascmc = swe.houses_ex(jd, lat, lon, b"P", 0)
        asc, mc = asc_mc(jd, lat, lon)
        worst_asc = max(worst_asc, angle_diff(ascmc[0], asc) / ARCSEC)
        worst_mc = max(worst_mc, angle_diff(ascmc[1], mc) / ARCSEC)
    # 1 second of time = 15" of sidereal time, and the formulas use slightly
    # different Earth-rotation models, so allow 15".
    assert worst_asc <= 15, f'Ascendant worst difference {worst_asc:.1f}"'
    assert worst_mc <= 15, f'Midheaven worst difference {worst_mc:.1f}"'


def test_full_chart_matches_french_models():
    """End to end: a real compute_chart() call, checked body by body."""
    c = compute_chart(date(1985, 7, 13), time(16, 45), 37.566, 126.978, "Asia/Seoul")
    jde = swe.julday(1985, 7, 13, 16.75 - 9) + swe.deltat(swe.julday(1985, 7, 13, 7.75))
    for p in c.planets:
        if p.name == "South Node":
            continue
        assert angle_diff(p.longitude, meeus_longitude(p.name, jde)) <= TOLERANCE[p.name] * ARCSEC, p.name
    asc, mc = asc_mc(swe.julday(1985, 7, 13, 7.75), 37.566, 126.978)
    assert angle_diff(c.ascendant.longitude, asc) <= 15 * ARCSEC
    assert angle_diff(c.midheaven.longitude, mc) <= 15 * ARCSEC


# ---------------------------------------------------------------- Vedic
LAHIRI_1956 = 23 + 15 / 60 + 0.658 / 3600  # official value, 21 March 1956


def test_lahiri_ayanamsa_follows_precession_from_its_official_value():
    """The Lahiri ayanamsa is its 1956 value carried forward by precession.

    We rebuild it with the French precession model and compare with the
    engine's value at random dates.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    jd_1956 = swe.julday(1956, 3, 21, 0.0)
    e_1956 = Epoch(jd_1956)
    # The official figure includes nutation; remove it to get the mean value.
    mean_1956 = LAHIRI_1956 - C.nutation_longitude(e_1956)()
    worst = 0.0
    for jd in random_jds(100, seed=7):
        lon, _ = C.precession_ecliptical(e_1956, Epoch(jd), Angle(mean_1956), Angle(0.0))
        theirs = lon() % 360
        ours = swe.get_ayanamsa_ex_ut(jd, swe.FLG_MOSEPH | swe.FLG_NONUT)[1]
        worst = max(worst, angle_diff(ours, theirs) / ARCSEC)
    assert worst <= 10, f'Ayanamsa worst difference {worst:.1f}"'
