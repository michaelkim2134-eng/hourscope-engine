"""Moon phase, tithi, sign changes and void-of-course."""

import random

import swisseph as swe

from hourscope_engine.lunar import (
    ASPECT_ANGLES, moon_aspect_times, moon_state, next_moon_ingress, phase_of, tithi_of,
    void_of_course_window,
)
from hourscope_engine.sky import PLANET_IDS, longitude_of, signed_diff

ECLIPSE_NEW_MOON = swe.julday(2024, 4, 8, 18 + 21 / 60)  # verified in test_charts.py


def test_tithi_and_phase_math():
    assert tithi_of(0.5)[:2] == (1, "Shukla Pratipada")
    assert tithi_of(130)[:2] == (11, "Shukla Ekadashi")
    assert tithi_of(170)[:2] == (15, "Purnima")
    assert tithi_of(185)[:3] == (16, "Krishna Pratipada", "Krishna")
    assert tithi_of(359)[:2] == (30, "Amavasya")
    assert phase_of(10) == "New Moon" and phase_of(95) == "First Quarter"
    assert phase_of(190) == "Full Moon" and phase_of(350) == "Balsamic"


def test_tithi_around_a_real_new_moon():
    assert moon_state(ECLIPSE_NEW_MOON + 1 / 24).tithi == "Shukla Pratipada"
    assert moon_state(ECLIPSE_NEW_MOON - 1 / 24).tithi == "Amavasya"


def test_moon_ingress_lands_on_a_sign_boundary():
    rng = random.Random(3)
    for _ in range(10):
        jd = 2447892.5 + rng.random() * 14600
        t = next_moon_ingress(jd)
        lon = longitude_of("Moon", t)[0]
        assert min(lon % 30, 30 - lon % 30) < 0.001
        assert 0 < t - jd < 2.8  # the Moon spends about 2.5 days in a sign


def test_aspect_times_are_exact():
    begin = ECLIPSE_NEW_MOON - 2
    for t, planet, angle in moon_aspect_times(begin, begin + 3):
        sep = signed_diff(longitude_of("Moon", t)[0], longitude_of(planet, t)[0])
        assert min(abs(abs(sep) - angle), 360 - abs(abs(sep) - angle)) < 1 / 3600


def test_void_of_course_has_no_aspects_inside_it():
    """Brute-force scan, independent of the search used by the engine."""
    rng = random.Random(11)
    planets = [p for p in PLANET_IDS if p != "Moon"]
    for _ in range(6):
        jd = 2447892.5 + rng.random() * 14600
        begin, start, end = void_of_course_window(jd)
        assert begin <= start <= end
        step = 10 / 1440
        t = start + 1 / 1440
        prev = None
        while t < end - 1 / 1440:
            moon = longitude_of("Moon", t)[0]
            now = {(p, a): signed_diff(abs(signed_diff(moon, longitude_of(p, t)[0])), a)
                   for p in planets for a in ASPECT_ANGLES}
            if prev:
                for k, v in now.items():
                    assert not (abs(v) < 5 and abs(prev[k]) < 5 and (v > 0) != (prev[k] > 0)), (k, t)
            prev = now
            t += step


def test_moon_state_vedic_has_nakshatra():
    s = moon_state(ECLIPSE_NEW_MOON, sidereal=True)
    assert s.nakshatra is not None
    assert moon_state(ECLIPSE_NEW_MOON).nakshatra is None
