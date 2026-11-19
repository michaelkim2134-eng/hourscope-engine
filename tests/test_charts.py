"""Chart accuracy (ground rule 2).

Three kinds of checks:
1. Reference charts: published positions for real people (Astro-Databank,
   Rodden rating AA/A). Add more to REFERENCE_CHARTS as they are collected.
2. Sky checks: well-documented astronomical moments (equinoxes, eclipses)
   where we know exactly where the Sun and Moon must be.
3. Vedic checks: the ayanamsa and the Sun's sidereal sign changes
   (sankrantis) that Indian calendars publish.
"""

from datetime import date, time

import pytest

from hourscope_engine import compute_chart
from hourscope_engine.chart import SIGNS, _position
from hourscope_engine.timeconv import local_to_utc

ARCMIN = 1 / 60


def sign_lon(sign: str, deg: int, minutes: int) -> float:
    return SIGNS.index(sign) * 30 + deg + minutes / 60


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


# ---------------------------------------------------------------- reference charts
# Each entry is copied from the person's Astro-Databank (ADB) page.
# Positions there are given to the arcminute, and birthplace coordinates to
# the arcminute, so we allow 2' for Sun/Moon and 4' for the angles.
# adb_offset is the UTC offset ADB used (its "Timezone" line), in hours.
# Two checks per person:
#   1. our automatic time zone lookup gives the same offset ADB used;
#   2. our positions match ADB's.
def dm(d: int, m: int, s: float = 0) -> float:
    return d + m / 60 + s / 3600


REFERENCE_CHARTS = [
    dict(
        who="Albert Einstein (ADB AA, 1879, local mean time)",
        date=date(1879, 3, 14), time=time(11, 30),
        lat=dm(48, 24), lon=dm(10, 0), tz="Europe/Berlin",
        adb_offset=dm(10, 0) / 15,  # "LMT m10e0"
        expect={"Sun": ("Pisces", 23, 30), "Moon": ("Sagittarius", 14, 32),
                "Ascendant": ("Cancer", 11, 39)},
    ),
    dict(
        who="Jawaharlal Nehru (ADB A, 1889, Madras time)",
        date=date(1889, 11, 14), time=time(23, 30),
        lat=dm(25, 27), lon=dm(81, 51), tz="Asia/Kolkata",
        adb_offset=dm(80, 17, 30) / 15,  # "MMT m80e1730"
        expect={"Sun": ("Scorpio", 22, 36), "Moon": ("Leo", 10, 28),
                "Ascendant": ("Leo", 22, 33)},
    ),
    dict(
        who="Marilyn Monroe (ADB AA, 1926, PST)",
        date=date(1926, 6, 1), time=time(9, 30),
        lat=dm(34, 3), lon=-dm(118, 15), tz="America/Los_Angeles",
        adb_offset=-8,  # "PST h8w"
        expect={"Sun": ("Gemini", 10, 27), "Moon": ("Aquarius", 19, 6),
                "Ascendant": ("Leo", 13, 4)},
    ),
    dict(
        who="Steve Jobs (ADB AA, 1955, PST)",
        date=date(1955, 2, 24), time=time(19, 15),
        lat=dm(37, 47), lon=-dm(122, 25), tz="America/Los_Angeles",
        adb_offset=-8,  # "PST h8w"
        expect={"Sun": ("Pisces", 5, 45), "Moon": ("Aries", 7, 45),
                "Ascendant": ("Virgo", 22, 18)},
    ),
    dict(
        who="Barack Obama (ADB AA, 1961, Hawaii)",
        date=date(1961, 8, 4), time=time(19, 24),
        lat=dm(21, 18), lon=-dm(157, 52), tz="Pacific/Honolulu",
        adb_offset=-10,  # "AHST h10w"
        expect={"Sun": ("Leo", 12, 33), "Moon": ("Gemini", 3, 21),
                "Ascendant": ("Aquarius", 18, 3)},
    ),
]


@pytest.mark.parametrize("ref", REFERENCE_CHARTS, ids=lambda r: r["who"])
def test_reference_time_zone(ref):
    r = local_to_utc(ref["date"], ref["time"], ref["tz"], ref["lon"])
    got_hours = r.utc_offset.total_seconds() / 3600
    assert abs(got_hours - ref["adb_offset"]) < 1 / 3600, f"offset {got_hours:.4f}h ({r.abbreviation})"


@pytest.mark.parametrize("ref", REFERENCE_CHARTS, ids=lambda r: r["who"])
def test_reference_chart(ref):
    # Use ADB's offset so this checks the astronomy on its own.
    c = compute_chart(ref["date"], ref["time"], ref["lat"], ref["lon"], ref["tz"],
                      manual_utc_offset_hours=ref["adb_offset"])
    for body, (sign, d, m) in ref["expect"].items():
        got = c.ascendant if body == "Ascendant" else c.midheaven if body == "Midheaven" else c.planet(body)
        tol = 4 * ARCMIN if body in ("Ascendant", "Midheaven") else 2 * ARCMIN
        assert angle_diff(got.longitude, sign_lon(sign, d, m)) <= tol, f"{body}: got {got.dms}"


# ---------------------------------------------------------------- sky checks
def chart_at_utc(d: date, t: time, system="western"):
    # Greenwich, so local time = UTC.
    return compute_chart(d, t, 51.4769, 0.0, "Etc/UTC", system=system)


def test_march_equinox_2000_sun_at_0_aries():
    # Equinox: 2000-03-20 07:35 UTC. The Sun moves about 1' every 24 minutes.
    c = chart_at_utc(date(2000, 3, 20), time(7, 35))
    assert angle_diff(c.planet("Sun").longitude, 0.0) <= 2 * ARCMIN


def test_june_solstice_2021_sun_at_0_cancer():
    # Solstice: 2021-06-21 03:32 UTC.
    c = chart_at_utc(date(2021, 6, 21), time(3, 32))
    assert angle_diff(c.planet("Sun").longitude, 90.0) <= 2 * ARCMIN


def test_total_solar_eclipse_2024_sun_and_moon_together():
    # New moon of the 8 April 2024 eclipse: 18:21 UTC, 19° Aries.
    c = chart_at_utc(date(2024, 4, 8), time(18, 21))
    sun, moon = c.planet("Sun"), c.planet("Moon")
    assert sun.sign == "Aries" and int(sun.sign_degree) == 19
    assert angle_diff(sun.longitude, moon.longitude) <= 0.1


def test_outer_planet_retrograde_flag():
    # Every year Saturn is retrograde for a stretch; in mid-August 2023 it was.
    c = chart_at_utc(date(2023, 8, 15), time(12, 0))
    assert c.planet("Saturn").retrograde
    assert not c.planet("Sun").retrograde


# ---------------------------------------------------------------- Vedic checks
def test_lahiri_ayanamsa_at_j2000():
    # Lahiri ayanamsa at 1 Jan 2000 is 23°51'.
    c = chart_at_utc(date(2000, 1, 1), time(12, 0), system="vedic")
    assert abs(c.ayanamsa - (23 + 51 / 60)) <= 2 * ARCMIN


def test_lahiri_ayanamsa_official_definition():
    # India's Calendar Reform Committee fixed Lahiri at 23°15'00.658" on 21 March 1956.
    c = chart_at_utc(date(1956, 3, 21), time(0, 0), system="vedic")
    assert abs(c.ayanamsa - (23 + 15 / 60 + 0.658 / 3600)) <= 1 / 3600


def test_vedic_is_tropical_minus_ayanamsa():
    w = chart_at_utc(date(1990, 3, 14), time(6, 20))
    v = chart_at_utc(date(1990, 3, 14), time(6, 20), system="vedic")
    for name in ("Sun", "Moon", "Mars", "Saturn"):
        assert angle_diff(w.planet(name).longitude - v.ayanamsa, v.planet(name).longitude) < 1 / 3600


def test_makar_sankranti_2024():
    # The Sun entered sidereal Capricorn on the night of 14/15 Jan 2024.
    assert chart_at_utc(date(2024, 1, 13), time(12), "vedic").planet("Sun").sign == "Sagittarius"
    assert chart_at_utc(date(2024, 1, 15), time(12), "vedic").planet("Sun").sign == "Capricorn"


def test_mesha_sankranti_2024():
    # The Sun entered sidereal Aries (Indian solar new year) on 13 Apr 2024.
    assert chart_at_utc(date(2024, 4, 12), time(12), "vedic").planet("Sun").sign == "Pisces"
    assert chart_at_utc(date(2024, 4, 15), time(12), "vedic").planet("Sun").sign == "Aries"


def test_rahu_ketu_opposite_and_retrograde():
    v = chart_at_utc(date(2010, 5, 1), time(0), system="vedic")
    rahu, ketu = v.planet("Rahu"), v.planet("Ketu")
    assert angle_diff(rahu.longitude + 180, ketu.longitude) < 1e-9
    assert rahu.retrograde  # the mean node always moves backwards


@pytest.mark.parametrize(
    "lon, nakshatra, pada, lord",
    [
        (0.0, "Ashwini", 1, "Ketu"),
        (3 + 20 / 60 + 0.001, "Ashwini", 2, "Ketu"),
        (13 + 20 / 60 + 0.001, "Bharani", 1, "Venus"),
        (120.0 - 0.001, "Ashlesha", 4, "Mercury"),
        (120.0, "Magha", 1, "Ketu"),
        (359.999, "Revati", 4, "Mercury"),
    ],
)
def test_nakshatra_boundaries(lon, nakshatra, pada, lord):
    p = _position("X", lon, 1.0, vedic=True)
    assert (p.nakshatra, p.pada, p.nakshatra_lord) == (nakshatra, pada, lord)


def test_vedic_whole_sign_houses():
    v = compute_chart(date(1879, 3, 14), time(11, 30), 48.4, 10.0, "Europe/Berlin", system="vedic")
    assert v.house_system == "Whole Sign"
    asc_sign = int(v.ascendant.longitude // 30)
    for p in v.planets:
        assert p.house == (int(p.longitude // 30) - asc_sign) % 12 + 1
    assert all(c % 30 == pytest.approx(0, abs=1e-9) for c in v.house_cusps)


# ---------------------------------------------------------------- behaviour
def test_unknown_birth_time_hides_houses_and_ascendant():
    c = compute_chart(date(1990, 3, 14), None, 37.566, 126.978, "Asia/Seoul")
    assert not c.time_known
    assert c.ascendant is None and c.midheaven is None and c.house_cusps is None
    assert all(p.house is None for p in c.planets)
    assert c.local_time.endswith("12:00:00")
    assert any("unknown" in w.lower() for w in c.warnings)


def test_placidus_falls_back_near_the_pole():
    c = compute_chart(date(2000, 1, 1), time(12), 78.22, 15.65, "Arctic/Longyearbyen")
    assert c.house_system in ("Placidus", "Porphyry")
    assert c.ascendant is not None


def test_placidus_houses_contain_planets_in_order():
    c = compute_chart(date(1879, 3, 14), time(11, 30), 48.4, 10.0, "Europe/Berlin")
    assert c.house_system == "Placidus"
    assert angle_diff(c.house_cusps[0], c.ascendant.longitude) < 1e-6
    assert angle_diff(c.house_cusps[9], c.midheaven.longitude) < 1e-6
    assert all(1 <= p.house <= 12 for p in c.planets)


def test_western_aspects_match_planet_separations():
    from hourscope_engine.chart import ASPECTS

    c = compute_chart(date(1879, 3, 14), time(11, 30), 48.4, 10.0, "Europe/Berlin")
    angles = {k: (a, o) for k, a, o in ASPECTS}
    found = {(a.a, a.b): a for a in c.aspects}
    assert found, "expected some aspects"
    names = [p.name for p in c.planets]
    for i, p in enumerate(c.planets):
        for q in c.planets[i + 1:]:
            if {p.name, q.name} == {"North Node", "South Node"}:
                assert (p.name, q.name) not in found
                continue
            sep = angle_diff(p.longitude, q.longitude)
            hits = [k for k, (ang, orb) in angles.items() if abs(sep - ang) <= orb]
            got = found.get((p.name, q.name))
            if hits:
                assert got is not None and got.kind in hits, (p.name, q.name, sep)
            else:
                assert got is None, (p.name, q.name, sep)
    assert c.aspects[0].a in names


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        compute_chart(date(2000, 1, 1), time(12), 95.0, 0.0)
    with pytest.raises(ValueError):
        compute_chart(date(2000, 1, 1), time(12), 0.0, 0.0, system="chinese")  # type: ignore[arg-type]
