def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_web(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (307, 308)
    assert response.headers["location"] == "/web"


def test_web_page_served(client) -> None:
    response = client.get("/web")
    assert response.status_code == 200
    assert '<html lang="zh-Hant-TW">' in response.text
    assert "<title>廁所地圖</title>" in response.text


def test_meta_endpoint_shape(client) -> None:
    response = client.get("/v1/meta")
    assert response.status_code == 200

    body = response.json()
    assert "lastSyncedAt" in body
    assert body["coverage"] == ["Taipei", "New Taipei"]
    assert body["version"] == "v1"


def test_toilets_endpoint_with_filter(client) -> None:
    response = client.get("/v1/toilets", params={"city": "taipei", "limit": 10})
    assert response.status_code == 200

    body = response.json()
    assert "items" in body
    assert "total" in body
    assert all(item["city"] == "Taipei" for item in body["items"])


def test_districts_endpoint_returns_items(client) -> None:
    response = client.get("/v1/districts", params={"city": "taipei"})
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert all(isinstance(item, str) for item in body["items"])


def test_nearby_endpoint_requires_lat_lng(client) -> None:
    response = client.get("/v1/toilets/nearby")
    assert response.status_code == 422


def test_detail_endpoint_not_found(client) -> None:
    response = client.get("/v1/toilets/not_exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Toilet not found"


def test_toilets_endpoint_gender_filter(client) -> None:
    response = client.get("/v1/toilets", params={"has_women_toilet": "true", "limit": 20})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["hasWomenToilet"] is True for item in items)


def test_toilets_endpoint_bbox_filter(client) -> None:
    seed = client.get("/v1/toilets", params={"limit": 1})
    assert seed.status_code == 200
    first = seed.json()["items"][0]
    lat = first["lat"]
    lng = first["lng"]

    bbox = f"{lng - 0.002},{lat - 0.002},{lng + 0.002},{lat + 0.002}"
    response = client.get("/v1/toilets", params={"bbox": bbox, "limit": 100})
    assert response.status_code == 200
    assert any(item["id"] == first["id"] for item in response.json()["items"])


def test_toilets_endpoint_aggregate_param(client) -> None:
    response = client.get("/v1/toilets", params={"aggregate": "true", "limit": 20})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all("sourceCount" in item for item in items)
