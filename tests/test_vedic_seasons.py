"""Vedic seasons: Ashtakavarga checksums, gochara with vedha, Sade Sati, dashas."""

from datetime import datetime, timezone
import random

import pytest

from hourscope_engine.chart import compute_chart
from hourscope_engine.vedic_seasons import SEVEN, ashtakavarga, vedic_seasons

from test_insights import EINSTEIN


def test_ashtakavarga_checksums_hold_for_any_chart():
    rng = random.Random(7)
    for _ in range(200):
        signs = {n: rng.randrange(12) for n in SEVEN + ["Ascendant"]}
        av = ashtakavarga(signs)      # raises if any planet's total is wrong
        assert sum(av["sav"]) == 337
        assert all(0 <= b <= 8 for row in av["bav"].values() for b in row)


def test_einstein_vedic_seasons():
    v = vedic_seasons(compute_chart(**EINSTEIN, system="vedic"), datetime(1950, 1, 1, tzinfo=timezone.utc))
    assert v.ashtakavarga and len(v.ashtakavarga["sav"]) == 12
    assert {g["planet"] for g in v.gochara} == set(SEVEN) | {"Rahu", "Ketu"}
    for g in v.gochara:
        assert g["status"] in {"favourable", "blocked", "challenging"}
        assert (g["status"] == "blocked") == (g["blocked_by"] is not None)
    # Sade Sati comes roughly every 29.5 years and lasts about 7.5.
    eps = v.sade_sati["episodes"]
    assert len(eps) >= 2
    first = eps[0]
    years = (datetime.fromisoformat(first["to"]) - datetime.fromisoformat(first["from"])).days / 365.25
    assert 6.0 < years < 9.0 or first["from"] <= "1879-06-01"     # the first may already be running at birth
    starts = [datetime.fromisoformat(e["from"]) for e in eps[1:3]]
    if len(starts) == 2:
        assert 27 < (starts[1] - starts[0]).days / 365.25 < 32
    assert v.dashas["pratyantar"] and len(v.dashas["pratyantars"]) == 9
    assert v.yogini["current"]["yogini"] in {"Mangala", "Pingala", "Dhanya", "Bhramari", "Bhadrika", "Ulka", "Siddha", "Sankata"}


def test_rejects_western_chart():
    with pytest.raises(ValueError):
        vedic_seasons(compute_chart(**EINSTEIN), datetime(1950, 1, 1, tzinfo=timezone.utc))


# ---- Double transits (Jupiter and Saturn both touching a sign)
from hourscope_engine.vedic_seasons import double_signs, double_transits, touched, JUPITER_ASPECTS, SATURN_ASPECTS
from hourscope_engine.sky import jd_from_datetime


def test_aspect_sets():
    # Jupiter in Cancer (index 3): Cancer, Scorpio, Capricorn, Pisces.
    assert touched(3, JUPITER_ASPECTS) == {3, 7, 9, 11}
    # Saturn in Pisces (11): Pisces, Taurus, Virgo, Sagittarius.
    assert touched(11, SATURN_ASPECTS) == {11, 1, 5, 8}


def test_mid_november_2026_activates_sagittarius():
    # 14 Nov 2026: sidereal Jupiter has just entered Leo (1.5 deg) and Saturn is in Pisces (14 deg).
    # Jupiter's 5th aspect from Leo and Saturn's 10th from Pisces both land on Sagittarius.
    from datetime import datetime, timezone
    assert double_signs(jd_from_datetime(datetime(2026, 11, 14, tzinfo=timezone.utc))) == {8}


def test_windows_are_consistent():
    from datetime import date, datetime, time, timedelta, timezone
    from hourscope_engine.chart import compute_chart
    c = compute_chart(date(1990, 3, 14), time(8, 30), 37.57, 126.98, "Asia/Seoul", system="vedic")
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    d = double_transits(c, now, years=3)
    assert [x["sign"] for x in d["now"]] == ["Sagittarius"]
    assert d["now"][0]["house_from_lagna"] is not None and d["now"][0]["house_from_moon"] is not None
    assert d["houses_from"] == "lagna"
    assert any(w["ongoing"] and w["sign"] == "Sagittarius" for w in d["windows"])
    for w in d["windows"]:
        assert w["to"] is None or w["from"] <= w["to"]
        # The middle of every closed window really is double-activated.
        if w["to"] and w["from"] != w["to"]:
            a, b = datetime.fromisoformat(w["from"]), datetime.fromisoformat(w["to"])
            mid = (a + (b - a) / 2).replace(tzinfo=timezone.utc)
            assert w["sign"] in [__import__("hourscope_engine.chart", fromlist=["SIGNS"]).SIGNS[i] for i in double_signs(jd_from_datetime(mid))]
    # Without a birth time, houses are counted from the Moon only (rule 4).
    u = compute_chart(date(1990, 3, 14), None, 37.57, 126.98, "Asia/Seoul", system="vedic")
    du = double_transits(u, now, years=1)
    assert all(x["house_from_lagna"] is None for x in du["now"]) and du["houses_from"] == "moon"


# ---- Kakshya (Ashtakavarga sub-divisions)
from hourscope_engine.vedic_seasons import BAV, KAKSHYA_LORDS, ashtakavarga, contributors, kakshya_detail, kakshya_of


def test_kakshya_slices():
    assert kakshya_of(0.0) == (0, "Saturn")
    assert kakshya_of(3.74) == (0, "Saturn")
    assert kakshya_of(3.76) == (1, "Jupiter")
    assert kakshya_of(29.99) == (7, "Ascendant")
    assert kakshya_of(30 * 5 + 15.0) == (4, "Venus")  # 15 deg into any sign is the 5th slice


def test_contributors_add_up_to_the_ashtakavarga():
    signs = {"Sun": 0, "Moon": 3, "Mars": 6, "Mercury": 1, "Jupiter": 8, "Venus": 11, "Saturn": 9, "Ascendant": 4}
    av = ashtakavarga(signs)
    for planet in BAV:
        for sign in range(12):
            assert len(contributors(signs, planet, sign)) == av["bav"][planet][sign]


def test_kakshya_detail_is_consistent():
    from datetime import datetime, timezone
    from hourscope_engine.sky import datetime_from_jd, longitude_of
    signs = {"Sun": 0, "Moon": 3, "Mars": 6, "Mercury": 1, "Jupiter": 8, "Venus": 11, "Saturn": 9, "Ascendant": 4}
    jd = jd_from_datetime(datetime(2026, 11, 14, tzinfo=timezone.utc))
    for planet in ("Jupiter", "Saturn", "Sun"):
        k = kakshya_detail(planet, signs, jd)
        lon = longitude_of(planet, jd, True)[0]
        assert k["lord"] == KAKSHYA_LORDS[k["index"] - 1] == kakshya_of(lon)[1]
        assert k["has_bindu"] == (k["lord"] in contributors(signs, planet, int(lon // 30)))
        assert k["until"] and k["until"] > "2026-11-14"
        if "next_bindu" in k and k["next_bindu"]:
            # Just after that moment the planet is in a slice whose ruler does give a bindu.
            t = jd_from_datetime(datetime.fromisoformat(k["next_bindu"])) + 0.01
            l2 = longitude_of(planet, t, True)[0]
            assert kakshya_of(l2)[1] in contributors(signs, planet, int(l2 // 30))
