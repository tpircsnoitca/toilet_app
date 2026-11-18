import json

import pytest

from app.core.db import connect_db


@pytest.mark.parametrize("nearby", [False, True])
@pytest.mark.parametrize(
    "required,diaper,expected",
    [
        (["accessible"], None, ["tp_001"]),
        (["gender_friendly"], None, ["tp_001", "ntpc_001"]),
        (["accessible", "gender_friendly"], "true", ["tp_001"]),
        (["accessible", "gender_friendly"], "false", []),
        (["not_a_known_type"], None, []),
        ([], None, ["tp_001", "ntpc_001"]),
    ],
)
def test_combined_facility_filters(client, nearby, required, diaper, expected):
    with connect_db() as conn:
        conn.execute(
            "UPDATE toilets SET toilet_types = ? WHERE id = 'tp_001'",
            (json.dumps(["male", "female", "accessible", "gender_friendly"]),),
        )
        conn.execute(
            "UPDATE toilets SET toilet_types = ? WHERE id = 'ntpc_001'",
            (json.dumps(["gender_friendly"]),),
        )
        conn.commit()
    params = [("toilet_types", value) for value in required]
    if diaper is not None:
        params.append(("has_diaper_table", diaper))
    if nearby:
        params.extend([("lat", "25.03"), ("lng", "121.49"), ("radius_m", "5000")])
    response = client.get("/v1/toilets/nearby" if nearby else "/v1/toilets", params=params)
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == set(expected)


def test_single_type_filter_remains_compatible(client):
    response = client.get("/v1/toilets", params={"toilet_type": "accessible"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["tp_001"]
