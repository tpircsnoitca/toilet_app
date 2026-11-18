def test_smoke_core_discovery_flow(client) -> None:
    # Step 1: service metadata is available
    meta = client.get("/v1/meta")
    assert meta.status_code == 200

    # Step 2: request nearby toilets around central Taipei
    nearby = client.get(
        "/v1/toilets/nearby",
        params={"lat": 25.0478, "lng": 121.5170, "radius_m": 3000},
    )
    assert nearby.status_code == 200

    payload = nearby.json()
    assert payload["total"] >= 1
    first = payload["items"][0]
    assert "id" in first and first["id"]

    # Step 3: fetch detail for returned toilet id
    detail = client.get(f"/v1/toilets/{first['id']}")
    assert detail.status_code == 200

    detail_body = detail.json()
    assert detail_body["id"] == first["id"]
    assert "openingHours" in detail_body
    assert len(detail_body["openingHours"]) == 7
