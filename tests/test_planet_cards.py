"""Planet report cards: dignity layers, accidental strength, dispositors, keynotes."""

from hourscope_engine.chart import SIGNS, compute_chart
from hourscope_engine.insights import sect_and_fortune
from hourscope_engine.planet_cards import CHALDEAN, TERMS, essential_layers, face_ruler, planet_cards, sign_relation, term_ruler

from test_insights import EINSTEIN


def test_term_and_face_tables():
    for sign, bounds in TERMS.items():
        ups = [u for _, u in bounds]
        assert ups == sorted(ups) and ups[-1] == 30 and len(bounds) == 5, sign
    assert term_ruler("Aries", 3) == "Jupiter" and term_ruler("Aries", 29) == "Saturn"
    assert face_ruler(5) == "Mars" and face_ruler(15) == "Sun" and face_ruler(25) == "Venus"   # Aries decans
    assert face_ruler(355) == CHALDEAN[35 % 7] == "Mars"                                       # last decan of Pisces


def test_essential_layers():
    sun_leo = essential_layers("Sun", SIGNS.index("Leo") * 30 + 5, day=True)
    assert "domicile" in sun_leo["layers"] and "triplicity" in sun_leo["layers"] and sun_leo["score"] >= 8
    venus_aries = essential_layers("Venus", 15, day=True)
    assert "detriment" in venus_aries["layers"] and venus_aries["score"] <= -5 + 3   # at most a minor layer offsets it
    sat_aries = essential_layers("Saturn", 4, day=True)
    assert "fall" in sat_aries["layers"] and sat_aries["peregrine"] is True


def test_sign_relation():
    assert sign_relation("Sun", "Aries") == "friend"      # Mars is the Sun's friend
    assert sign_relation("Sun", "Libra") == "enemy"       # Venus
    assert sign_relation("Sun", "Leo") == "own"
    assert sign_relation("Mercury", "Sagittarius") == "neutral"


def test_einstein_cards():
    c = compute_chart(**EINSTEIN)
    sect, _ = sect_and_fortune(c)
    pc = planet_cards(c, sect)
    assert pc.sect == "day" and pc.chart_ruler == "Moon"            # Cancer rising, born late morning
    sun = next(x for x in pc.cards if x["planet"] == "Sun")
    assert sun["comfort"]["term_lord"] == "Mars" and sun["comfort"]["face_lord"] == "Mars"
    assert sun["comfort"]["peregrine"] is True and sun["team"] == "in sect"
    assert len(pc.keynotes) == 5 and pc.keynotes[0]["score"] == 10
    assert set(pc.dispositors["chains"]) == {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    assert pc.dispositors["final"] or pc.dispositors["loops"] or pc.dispositors["self_ruled"]
    assert pc.themes and 1 <= pc.themes[0]["letter"] <= 12


def test_vedic_cards():
    pc = planet_cards(compute_chart(**EINSTEIN, system="vedic"))
    assert pc.sect is None
    card = pc.cards[0]
    assert set(card["comfort"]) == {"dignity", "relation", "vargottama"}
