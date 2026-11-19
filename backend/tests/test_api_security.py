from unittest.mock import Mock

import pytest

from app import main
from app.services.toilet_service import list_toilets


@pytest.mark.parametrize("token", [None, "", "   "])
def test_admin_sync_disabled_without_configured_token(client, monkeypatch, token):
    if token is None:
        monkeypatch.delenv("TOILET_ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TOILET_ADMIN_TOKEN", token)
    sync = Mock()
    monkeypatch.setattr(main, "sync_moenv_data", sync)

    response = client.post("/v1/admin/sync", headers={"Authorization": "Bearer guessed"})

    assert response.status_code == 503
    sync.assert_not_called()


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer incorrect", "Basic secret", "Bearer"],
)
def test_admin_sync_rejects_invalid_credentials(client, monkeypatch, authorization):
    monkeypatch.setenv("TOILET_ADMIN_TOKEN", "test-secret")
    sync = Mock()
    monkeypatch.setattr(main, "sync_moenv_data", sync)
    headers = {"Authorization": authorization} if authorization else {}

    response = client.post("/v1/admin/sync", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "test-secret" not in response.text
    sync.assert_not_called()


def test_admin_sync_accepts_valid_bearer_token(client, monkeypatch):
    monkeypatch.setenv("TOILET_ADMIN_TOKEN", "test-secret")
    sync = Mock(return_value={"syncedAt": "2026-11-10T00:00:00Z", "recordsUpserted": 1})
    monkeypatch.setattr(main, "sync_moenv_data", sync)

    response = client.post("/v1/admin/sync", headers={"Authorization": "Bearer test-secret"})

    assert response.status_code == 200
    assert response.json()["recordsUpserted"] == 1
    sync.assert_called_once_with()


@pytest.mark.parametrize(
    "bbox",
    [
        "nan,25,122,26",
        "121,25,inf,26",
        "-181,25,122,26",
        "121,-91,122,26",
        "121,25,181,26",
        "121,25,122,91",
        "122,25,121,26",
        "121,26,122,25",
        "121,25,122",
    ],
)
def test_invalid_bbox_is_rejected(client, bbox):
    assert client.get("/v1/toilets", params={"bbox": bbox}).status_code == 422
    assert client.post("/v1/toilets", json={"bbox": bbox}).status_code == 422


@pytest.mark.parametrize(
    "lat,lng", [(91, 121), (-91, 121), (25, 181), (25, -181), ("nan", 121), (25, "inf")]
)
def test_invalid_nearby_coordinates_are_rejected(client, lat, lng):
    response = client.get("/v1/toilets/nearby", params={"lat": lat, "lng": lng})
    assert response.status_code == 422
    response = client.post("/v1/toilets/nearby", json={"lat": lat, "lng": lng})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/v1/toilets", {"bbox": "-180,-90,180,90", "limit": 1}),
        ("/v1/toilets/nearby", {"lat": 25.0478, "lng": 121.517, "radius_m": 5000}),
    ],
)
def test_json_search_matches_legacy_search(client, path, location):
    filters = {**location, "aggregate": True, "gender": ["men", "women"]}
    legacy = client.get(path, params=filters)
    private = client.post(path, json=filters)

    assert legacy.status_code == private.status_code == 200
    assert legacy.json() == private.json()
    assert private.json()["items"]
    assert not private.request.url.query


def test_valid_coordinate_boundaries_are_accepted(client):
    assert client.get("/v1/toilets", params={"bbox": "-180,-90,180,90"}).status_code == 200
    response = client.get("/v1/toilets/nearby", params={"lat": 90, "lng": 180})
    assert response.status_code == 200


def test_list_result_limit_is_enforced(client, monkeypatch):
    items = list_toilets()
    monkeypatch.setattr(main, "list_toilets", lambda **kwargs: [items[0]] * 205)

    for params, expected_count in [({}, 200), ({"limit": 200}, 200), ({"limit": 1}, 1)]:
        response = client.get("/v1/toilets", params=params)
        assert response.status_code == 200
        assert len(response.json()["items"]) == expected_count

    for limit in (0, 201, 300, 500):
        assert client.get("/v1/toilets", params={"limit": limit}).status_code == 422
