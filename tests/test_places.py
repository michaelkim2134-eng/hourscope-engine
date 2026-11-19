from hourscope_engine.places import find_place, timezone_at


def test_find_city_with_country():
    ulm = find_place("Ulm, Germany")[0]
    assert ulm.country_code == "DE"
    assert ulm.timezone == "Europe/Berlin"
    assert abs(ulm.latitude - 48.4) < 0.1 and abs(ulm.longitude - 10.0) < 0.1


def test_ambiguous_city_narrowed_by_state():
    bay = find_place("Bay City, MI")[0]
    assert bay.timezone == "America/Detroit"


def test_accents_and_case_ignored():
    assert find_place("sao paulo")[0].country_code == "BR"


def test_unknown_place_returns_nothing():
    assert find_place("Nowhereville Zzz") == []


def test_timezone_from_coordinates():
    assert timezone_at(37.566, 126.978) == "Asia/Seoul"
    assert timezone_at(21.64, 69.61) == "Asia/Kolkata"
