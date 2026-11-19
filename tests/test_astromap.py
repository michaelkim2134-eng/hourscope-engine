"""Places: a point on a planet's line must show that planet on the relocated angle (rule 2)."""

from datetime import datetime

from hourscope_engine.astromap import CITIES, THEMES, acg_lines, astro_map, compass, influence, nearby_lines, relocated
from hourscope_engine.chart import compute_chart
from hourscope_engine.sky import jd_from_datetime

from test_insights import EINSTEIN


def lines_for(chart):
    return acg_lines(jd_from_datetime(datetime.fromisoformat(chart.utc_time)), lat_step=1.0)


def test_point_on_mc_line_puts_planet_on_the_midheaven():
    c = compute_chart(**EINSTEIN)
    lines = lines_for(c)
    for planet in ("Sun", "Venus", "Jupiter"):
        r = relocated(c, 30.0, lines[planet]["MC"])
        assert any(a["planet"] == planet and a["angle"] == "MC" and a["orb"] <= 1.5 for a in r["angular"]), (planet, r)


def test_point_on_rising_or_setting_line_has_the_planet_on_the_horizon():
    # Lines are in mundo: the planet is physically on the horizon there (true altitude ~0),
    # rising in the east or setting in the west. (Its ecliptic degree can differ from the
    # Ascendant by a few degrees when it has ecliptic latitude, as the Moon often does.)
    c = compute_chart(**EINSTEIN)
    lines = lines_for(c)
    for planet in ("Moon", "Saturn", "Venus", "Pluto"):
        for angle, east in (("ASC", True), ("DSC", False)):
            lat, lon = next(p for p in lines[planet][angle] if abs(p[0] - 40) < 0.6)
            body = next(x for x in compass(c, lat, lon) if x["planet"] == planet)
            assert abs(body["altitude"]) < 0.6, (planet, angle, body)
            assert (0 < body["bearing"] < 180) == east, (planet, angle, body)


def test_influence_curve_and_nearby():
    assert influence(100) == 1.0 and influence(800) == 0.0 and 0 < influence(475) < 1
    c = compute_chart(**EINSTEIN)
    lines = lines_for(c)
    near = nearby_lines(lines, 30.0, lines["Venus"]["MC"])
    assert near[0]["planet"] == "Venus" and near[0]["angle"] == "MC" and near[0]["km"] < 5


def test_full_map_and_compass():
    c = compute_chart(**EINSTEIN)
    m = astro_map(c, ("Princeton", 40.3573, -74.6672, "America/New_York"))
    assert set(m.lines) >= {"Sun", "Moon", "Venus", "Pluto"} and set(m.best) == set(THEMES)
    assert all(len(v) <= 6 for v in m.best.values())
    assert m.current["relocated"]["ascendant"] and m.birthplace["name"] == "Birthplace"
    comp = compass(c, 40.3573, -74.6672)
    assert len(comp) == 10 and all(0 <= x["bearing"] < 360 for x in comp)
    assert len(CITIES) >= 80


def test_mc_and_ic_lines_are_half_meridians():
    from hourscope_engine.astromap import distance_to_line
    c = compute_chart(**EINSTEIN)
    ln = lines_for(c)["Venus"]
    # A point on the IC line is far from the MC line (and vice versa).
    assert distance_to_line(20.0, ln["IC"], ln, "IC") < 5
    assert distance_to_line(20.0, ln["IC"], ln, "MC") > 5000
    near = nearby_lines(lines_for(c), 20.0, ln["IC"])
    assert not any(n["planet"] == "Venus" and n["angle"] == "MC" for n in near)



def test_relocated_chart_without_birth_time_has_no_angles_or_houses():
    """Rule 4: no birth time means no rising sign or houses, in any city."""
    c = compute_chart(**{**EINSTEIN, "birth_time": None})
    assert relocated(c, 40.7, -74.0) == {"ascendant": None, "midheaven": None, "sun_house": None, "moon_house": None, "angular": []}
