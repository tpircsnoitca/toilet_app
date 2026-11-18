from app.ingestion.sync_moenv import (
    _extract_district,
    _infer_gender_flags,
    _normalize_feature,
    _parse_hhmm,
)


def test_parse_hhmm_accepts_fullwidth_colon() -> None:
    assert _parse_hhmm("09：30") == "09:30"


def test_extract_district_from_address() -> None:
    assert _extract_district("臺北市中正區忠孝西路一段") == "中正區"


def test_normalize_feature_maps_core_fields() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [121.5, 25.0]},
        "properties": {
            "pid": "abc123",
            "ctrl_name": "Test Toilet",
            "ctrl_addr": "新北市板橋區中山路1號",
            "toilet_type": "4",
            "Equipment": "1",
            "MonStart": "全天開放",
            "MonEnd": "",
            "TueStart": "09:00",
            "TueEnd": "18:00",
            "WedStart": "09:00",
            "WedEnd": "18:00",
            "ThuStart": "09:00",
            "ThuEnd": "18:00",
            "FriStart": "09:00",
            "FriEnd": "18:00",
            "SatStart": "09:00",
            "SatEnd": "18:00",
            "SunStart": "09:00",
            "SunEnd": "18:00",
        },
    }

    normalized = _normalize_feature(feature, "New Taipei")
    assert normalized is not None
    assert normalized["id"] == "abc123"
    assert normalized["district"] == "板橋區"
    assert normalized["toilet_types"] == ["accessible"]
    assert normalized["has_diaper_table"] == 1
    assert len(normalized["opening_hours"]) == 7


def test_infer_gender_flags_from_name_hints() -> None:
    has_men, has_women = _infer_gender_flags("4", "Example 公廁男")
    assert has_men is True
    assert has_women is False
