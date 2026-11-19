"""Vedic dignity and yoga rules (Parashara, as given in Rao and Behari)."""

from types import SimpleNamespace

from hourscope_engine.chart import SIGNS
from hourscope_engine.insights import find_yogas, is_combust, vedic_dignity


def lon(sign: str, deg: float) -> float:
    return SIGNS.index(sign) * 30 + deg


def test_vedic_dignity_levels():
    assert vedic_dignity("Sun", lon("Aries", 10.3)) == "deep exaltation"
    assert vedic_dignity("Sun", lon("Aries", 25)) == "exaltation"
    assert vedic_dignity("Sun", lon("Leo", 5)) == "moolatrikona"
    assert vedic_dignity("Sun", lon("Leo", 25)) == "own sign"
    assert vedic_dignity("Sun", lon("Libra", 10)) == "deep debilitation"
    assert vedic_dignity("Sun", lon("Libra", 2)) == "debilitation"
    assert vedic_dignity("Sun", lon("Aquarius", 10)) is None          # no "detriment" in Vedic
    # Moon: exalted only in the first 3 degrees of Taurus, then moolatrikona.
    assert vedic_dignity("Moon", lon("Taurus", 0.5)) == "exaltation"
    assert vedic_dignity("Moon", lon("Taurus", 2.5)) == "deep exaltation"
    assert vedic_dignity("Moon", lon("Taurus", 10)) == "moolatrikona"
    # Mercury in Virgo: exaltation to 15, moolatrikona 15-20, own sign after.
    assert vedic_dignity("Mercury", lon("Virgo", 14.5)) == "deep exaltation"
    assert vedic_dignity("Mercury", lon("Virgo", 17)) == "moolatrikona"
    assert vedic_dignity("Mercury", lon("Virgo", 25)) == "own sign"
    assert vedic_dignity("Rahu", lon("Taurus", 10)) is None


def P(name: str, sign: str, deg: float = 15.0, retro: bool = False):
    return SimpleNamespace(name=name, sign=sign, longitude=lon(sign, deg), retrograde=retro)


def chart(asc: str | None = "Aries", **placements):
    base = {"Sun": "Aries", "Moon": "Aries", "Mars": "Aries", "Mercury": "Aries",
            "Jupiter": "Aries", "Venus": "Aries", "Saturn": "Aries"}
    base.update(placements)
    planets = [P(n, s) if isinstance(s, str) else P(n, *s) for n, s in base.items()]
    return SimpleNamespace(planets=planets,
                           ascendant=SimpleNamespace(sign=asc, longitude=lon(asc, 5)) if asc else None)


def yogas(c):
    return {y.name: y for y in find_yogas(c)}


def test_combustion_orbs():
    sun = P("Sun", "Leo", 10)
    assert is_combust(P("Jupiter", "Leo", 20), sun)            # 10 degrees, orb 11
    assert not is_combust(P("Jupiter", "Leo", 22), sun)        # 12 degrees
    assert is_combust(P("Venus", "Leo", 19), sun)              # 9 degrees, orb 10
    assert not is_combust(P("Venus", "Leo", 19, retro=True), sun)  # retrograde orb 8


def test_gajakesari_needs_a_strong_jupiter():
    # Jupiter in Cancer, the Moon in Aries: Jupiter 4th from the Moon, Sun far away.
    ok = chart(Moon="Aries", Jupiter="Cancer", Sun="Libra")
    assert "Gajakesari" in yogas(ok)
    debilitated = chart(Moon="Cancer", Jupiter="Capricorn", Sun="Libra")      # 7th from Moon but debilitated
    assert "Gajakesari" not in yogas(debilitated)
    enemy_sign = chart(Moon="Pisces", Jupiter="Gemini", Sun="Libra")          # Mercury's sign
    assert "Gajakesari" not in yogas(enemy_sign)
    combust = chart(Moon="Aries", Jupiter=("Cancer", 15), Sun=("Cancer", 20))
    assert "Gajakesari" not in yogas(combust)


def test_chandra_mangala_full_and_partial():
    assert yogas(chart(Moon="Taurus", Mars="Taurus"))["Chandra-Mangala"].strength == "full"
    assert yogas(chart(Moon="Taurus", Mars="Scorpio"))["Chandra-Mangala"].strength == "partial"


def test_kemadruma_and_its_cancellations():
    # Moon alone in Leo; everything else in Aquarius (7th from the Moon = an angle) -> cancelled.
    c = chart(asc="Aries", Moon="Leo", Sun="Aquarius", Mars="Aquarius", Mercury="Aquarius",
              Jupiter="Aquarius", Venus="Aquarius", Saturn="Aquarius")
    k = yogas(c)["Kemadruma"]
    assert k.strength == "cancelled" and "angle from the Moon" in k.note
    # Others in Sagittarius (5th from Leo Moon, 9th from Aries Asc): no angle anywhere; Moon in Leo is 5th from Aries.
    c2 = chart(asc="Aries", Moon="Leo", Sun="Sagittarius", Mars="Sagittarius", Mercury="Sagittarius",
               Jupiter="Sagittarius", Venus="Sagittarius", Saturn="Sagittarius")
    assert yogas(c2)["Kemadruma"].strength == "full"
    # Same, but the Moon is in an angle from the Ascendant (Leo rising) -> cancelled.
    c3 = chart(asc="Leo", Moon="Leo", Sun="Sagittarius", Mars="Sagittarius", Mercury="Sagittarius",
               Jupiter="Sagittarius", Venus="Sagittarius", Saturn="Sagittarius")
    assert yogas(c3)["Kemadruma"].strength == "cancelled"


def test_mahapurusha_uses_vedic_dignity():
    # Jupiter in Sagittarius 5 degrees (moolatrikona) in the 10th from Pisces rising.
    c = chart(asc="Pisces", Jupiter=("Sagittarius", 5), Moon="Taurus", Sun="Libra")
    assert "Hamsa (Pancha Mahapurusha)" in yogas(c)
