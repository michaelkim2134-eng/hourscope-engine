"""Soul Path (karma and purpose)."""

from datetime import datetime, timezone

from hourscope_engine.chart import compute_chart
from hourscope_engine.soul import soul_path

from test_insights import EINSTEIN

NOW = datetime(1950, 1, 1, tzinfo=timezone.utc)


def test_nodal_axis_and_cycle():
    s = soul_path(compute_chart(**EINSTEIN), NOW)
    north, south = s.nodes["north"]["sign"], s.nodes["south"]["sign"]
    assert s.nodes["axis"] == f"{north}-{south}"
    assert s.nodes["south"]["house"] == (s.nodes["north"]["house"] + 5) % 12 + 1
    returns = [e["age"] for e in s.nodal_cycle if e["kind"] == "return"]
    reversals = [e["age"] for e in s.nodal_cycle if e["kind"] == "reversal"]
    assert 18.0 < returns[0] < 19.3 and 36.6 < returns[1] < 38.0        # every ~18.6 years
    assert 8.7 < reversals[0] < 10.0


def test_saturn_cycle_and_phase():
    s = soul_path(compute_chart(**EINSTEIN), NOW)
    sat = s.saturn
    assert sat["sign"] == "Aries"
    first_return = next(e for e in sat["cycle"] if e["kind"] == "return")
    assert 28.5 < first_return["age"] < 30.5 and 1 <= len(first_return["passes"]) <= 3
    kinds = [e["kind"] for e in sat["cycle"][:4]]
    assert kinds == ["opening square", "opposition", "closing square", "return"]
    assert 0 <= sat["phase"]["percent"] < 100 and sat["phase"]["name"] in {"building", "testing", "harvest", "release"}


def test_polarity_mission_growth():
    s = soul_path(compute_chart(**EINSTEIN), NOW)
    assert s.polarity["sun"] == "Pisces" and s.polarity["moon"] == "Sagittarius"
    assert s.polarity["harmony"] == "tension"                               # water and fire
    assert set(s.mission["sign_cross"]) == {"cardinal", "fixed", "mutable"}
    # Cancer rising (3) + Mercury, Venus, Mars, Saturn in cardinal signs (2 each) = 11; Sun + Moon mutable = 6 + Uranus 1.
    assert s.mission["dominant"] == "cardinal" and s.mission["sign_cross"] == {"cardinal": 11, "fixed": 4, "mutable": 7}
    assert s.growth_planet and s.growth_planet["planet"] not in ("Sun", "Moon")
    assert s.vedic is None


def test_vedic_karakas_and_aims():
    s = soul_path(compute_chart(**EINSTEIN, system="vedic"), NOW)
    k = s.vedic["karakas"]
    assert [x["karaka"] for x in k][:2] == ["Atmakaraka", "Amatyakaraka"] and len(k) == 8
    assert all(a["degree"] >= b["degree"] for a, b in zip(k, k[1:]))
    assert s.vedic["atmakaraka"] == k[0]["planet"]
    assert sum(s.vedic["aims"].values()) in (99, 100, 101)


def test_unknown_time_hides_houses():
    kw = dict(EINSTEIN)
    kw["birth_time"] = None
    s = soul_path(compute_chart(**kw), NOW)
    assert s.nodes["north"]["house"] is None and s.mission["house_cross"] is None
    assert s.warnings
