from app.services.toilet_service import (
    _haversine_m,
    _polish_toilet_name,
    get_toilet,
    list_districts,
    list_toilets,
    nearby_toilets,
)


def test_haversine_returns_zero_for_same_point() -> None:
    assert _haversine_m(25.0478, 121.5170, 25.0478, 121.5170) == 0


def test_list_toilets_filters_city() -> None:
    results = list_toilets(city="taipei")
    assert results
    assert all(item.city == "Taipei" for item in results)


def test_list_toilets_filters_keyword() -> None:
    baseline = list_toilets()
    assert baseline
    keyword = baseline[0].name[:2]
    results = list_toilets(keyword=keyword)
    assert len(results) >= 1


def test_nearby_toilets_sorts_by_distance() -> None:
    results = nearby_toilets(lat=25.03, lng=121.50, radius_m=10000)
    assert len(results) >= 2
    distances = [item.distanceM for item in results if item.distanceM is not None]
    assert distances == sorted(distances)


def test_get_toilet_returns_none_for_unknown_id() -> None:
    assert get_toilet("missing") is None


def test_polish_toilet_name_removes_gender_and_floor() -> None:
    raw_name = "松山機場國際線-1F報到大廳東區-男廁所"
    assert _polish_toilet_name(raw_name) == "松山機場國際線 報到大廳東區"


def test_polish_toilet_name_removes_accessible_and_toilet_number() -> None:
    raw_name = "和信治癌中心醫院7947無障礙廁所"
    assert _polish_toilet_name(raw_name) == "和信治癌中心醫院"


def test_list_districts_returns_sorted_distinct_values() -> None:
    districts = list_districts(city="taipei")
    assert districts
    assert districts == sorted(set(districts))
