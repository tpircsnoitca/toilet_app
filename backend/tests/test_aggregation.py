import json
from unittest.mock import Mock

import pytest

from app.core.db import connect_db
from app.ingestion import sync_moenv
from app.services.aggregation import (
    FACILITIES,
    build_groups,
    initialize_archive,
    preserve_snapshot,
    published_groups,
)
from app.services.toilet_service import initialize_db


def row(id, name="Same toilet", address="No.1 Road", lat=25, lng=121):
    return dict(
        id=id,
        name=name,
        address=address,
        city="Taipei",
        district="中正區",
        lat=lat,
        lng=lng,
        toilet_types='["male"]',
        has_men_toilet=1,
        has_women_toilet=0,
        has_diaper_table=0,
        open_now=None,
        open_label="Unknown",
    )


def seed(rows):
    initialize_db()
    with connect_db() as conn:
        conn.execute("DELETE FROM opening_hours")
        conn.execute("DELETE FROM toilets")
        for r in rows:
            conn.execute(
                f"INSERT INTO toilets({','.join(r)}) VALUES({','.join('?' for _ in r)})",
                tuple(r.values()),
            )


def test_exact_matching_and_safety():
    rows = [
        row("a"),
        row("b", name="Ｓａｍｅ toilet "),
        row("c", name="Different toilet"),
        row("d", address=None),
        row("e", address=None),
        row("f", name="Far"),
        row("g", name="Far", lat=26),
    ]
    groups, report = build_groups(rows)
    assert sorted(g["sourceIds"] for g in groups) == [["a", "b"], ["c"], ["d"], ["e"], ["f"], ["g"]]
    assert report[0]["reason"] == "coordinate_spread"
    reverse, _ = build_groups(list(reversed(rows)))
    assert [(g["id"], g["sourceIds"]) for g in groups] == [
        (g["id"], g["sourceIds"]) for g in reverse
    ]


def hospital_rows():
    f = FACILITIES[0]
    a = row("a", f["prefix"] + "1F女", f["address"])
    a.update(toilet_types='["female"]', has_men_toilet=0, has_women_toilet=1)
    b = row("b", f["prefix"] + "第二棟2樓無障礙", f["address"])
    b.update(toilet_types='["accessible"]', has_men_toilet=0)
    return [a, b]


def test_nearby_facility_groups_keep_original_details_and_distinct_tenants(client):
    address = "臺北市中正區公園路30號"
    a = row("a", "麥當勞台北公園店1F-男廁", address)
    b = row("b", "麥當勞台北公園店2樓-女廁", address, lat=25.0001)
    b.update(
        toilet_types='["female","accessible"]',
        has_men_toilet=0,
        has_women_toilet=1,
        has_diaper_table=1,
    )
    seed([a, b, row("c", "其他餐廳1F-男廁", address)])
    items = client.get("/v1/toilets/nearby?aggregate=true&lat=25&lng=121").json()["items"]
    assert len(items) == 2
    group = next(x for x in items if x["sourceCount"] == 2)
    assert group["name"] == "麥當勞台北公園店"
    assert group["groupKind"] == "facility"
    assert group["symbolSources"] == {
        "male": ["a"],
        "female": ["b"],
        "accessible": ["b"],
        "diaper_table": ["b"],
    }
    assert [(r["name"], r["floor"]) for r in group["sourceRecords"]] == [
        (a["name"], "1F"),
        (b["name"], "2樓"),
    ]
    assert client.get("/v1/toilets/a").json()["name"] == a["name"]


def test_facility_suffix_keeps_room_codes_and_ambiguous_locations_separate():
    address = "新北市坪林區國中路1號"
    rows = [
        row("a", "金瓜寮-男廁", "新北市坪林區粗窟里無"),
        row("b", "金瓜寮-女廁", "新北市坪林區粗窟里無"),
        row("c", "服務中心B101-男廁", address),
        row("d", "服務中心B102-女廁", address),
        row("e", "商場1F-男廁", address),
        row("f", "商場1F-女廁", address, lat=26),
    ]
    groups, report = build_groups(rows)
    assert len(groups) == 6
    assert report[0]["sourceIds"] == ["e", "f"]


def test_single_record_card_uses_facility_title_and_preserves_floor_and_gender(client):
    original = "新莊區民有里辦公處1F-混合廁所"
    source = row("a", original, "新北市新莊區民有里民本街33巷8號1樓")
    source.update(toilet_types='["mixed"]', has_women_toilet=1)
    seed([source])
    item = client.get("/v1/toilets/nearby?aggregate=true&lat=25&lng=121").json()["items"][0]
    assert item["name"] == "新莊區民有里辦公處"
    assert item["sourceCount"] == 1
    assert item["floor"] == "1F"
    assert item["symbolSources"] == {"male": ["a"], "female": ["a"]}
    assert item["sourceRecords"][0]["name"] == original
    assert client.get("/v1/toilets/a").json()["name"] == original


def test_reviewed_market_groups_address_alias_and_does_not_route_to_outlier():
    market = FACILITIES[1]
    rows = [
        row("a", "漁夫巿集-2F男廁", market["address"], lat=24),
        row("b", "漁夫巿集-1F女廁", market["address"]),
        row("c", "漁夫巿集-1F無障礙", market["address_aliases"][0], lat=25.0001),
    ]
    for record in rows:
        record["city"] = market["city"]
    groups, report = build_groups(rows)
    assert len(groups) == 1
    assert groups[0]["sourceIds"] == ["a", "b", "c"]
    assert groups[0]["representativeId"] == "b"
    assert report[0]["mergedByReview"] is True


def test_hospital_preserves_sources_symbols_and_filters(client):
    seed(hospital_rows())
    response = client.get("/v1/toilets?aggregate=true").json()
    item = response["items"][0]
    assert response["total"] == 1
    assert item["sourceCount"] == 2
    assert item["groupKind"] == "facility"
    assert item["symbolSources"] == {"female": ["a"], "accessible": ["b"]}
    assert item["sourceRecords"][1]["building"] == "第二棟"
    assert item["sourceRecords"][1]["floor"] == "2樓"
    assert item["sourceRecords"][0]["name"].endswith("1F女")
    # Female + accessible in different toilets is not a matching toilet.
    assert (
        client.get(
            "/v1/toilets?aggregate=true&has_women_toilet=true&toilet_types=accessible"
        ).json()["items"]
        == []
    )
    filtered = client.get("/v1/toilets?aggregate=true&toilet_types=accessible").json()["items"][0]
    assert filtered["id"] == item["id"]
    assert filtered["matchingSourceIds"] == ["b"]
    assert len(filtered["sourceRecords"]) == 2
    assert client.get("/v1/toilets/a").json()["name"].endswith("1F女")
    nearby = client.get("/v1/toilets/nearby?aggregate=true&lat=25&lng=121").json()["items"]
    assert nearby[0]["id"] == item["id"]
    assert nearby[0]["distanceM"] == 0


def test_unknown_and_different_hours(client):
    seed(hospital_rows())
    with connect_db() as conn:
        for day in range(7):
            conn.execute("INSERT INTO opening_hours VALUES('a',?,?,?,0)", (day, "00:01", "00:02"))
    # At any time other than this one minute, known closed + unknown must be unknown.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.services import toilet_service

    original = toilet_service._local_now
    try:
        toilet_service._local_now = lambda: datetime(
            2026, 11, 17, 12, tzinfo=ZoneInfo("Asia/Taipei")
        )
        item = client.get("/v1/toilets?aggregate=true").json()["items"][0]
        assert item["openNow"] is None
        assert item["openLabel"] == "Hours vary by toilet"
        assert client.get("/v1/toilets?aggregate=true&open_now=true").json()["items"] == []
    finally:
        toilet_service._local_now = original


@pytest.mark.parametrize("path", ["/v1/toilets?", "/v1/toilets/nearby?lat=25&lng=121&"])
def test_gender_choices_match_any_but_facilities_must_match_the_same_record(client, path):
    men, women = row("men"), row("women")
    women.update(has_men_toilet=0, has_women_toilet=1, toilet_types='["female"]')
    accessible = row("accessible")
    accessible.update(has_men_toilet=0, toilet_types='["accessible"]')
    friendly = row("friendly", name="Separate facility")
    friendly.update(has_men_toilet=0, toilet_types='["gender_friendly"]')
    seed([men, women, accessible, friendly])

    url = path + "aggregate=true"
    items = client.get(url + "&gender=men&gender=women&gender=gender_friendly").json()["items"]
    assert {tuple(item["matchingSourceIds"]) for item in items} == {("men", "women"), ("friendly",)}
    assert (
        client.get(url + "&gender=men&gender=women&toilet_types=accessible").json()["items"] == []
    )
    unfiltered = client.get(url + "&toilet_types=accessible").json()["items"]
    assert unfiltered[0]["matchingSourceIds"] == ["accessible"]
    assert client.get(url + "&gender=invalid").status_code == 422


def test_versions_archive_sources_and_do_not_modify_source_rows():
    seed(hospital_rows())
    with connect_db() as conn:
        before = [dict(r) for r in conn.execute("SELECT * FROM toilets ORDER BY id")]
    first, groups = published_groups()
    assert published_groups()[0] == first
    with connect_db() as conn:
        assert before == [dict(r) for r in conn.execute("SELECT * FROM toilets ORDER BY id")]
        conn.execute("UPDATE toilets SET has_diaper_table=1 WHERE id='b'")
    second, next_groups = published_groups()
    assert first != second
    assert groups[0]["id"] == next_groups[0]["id"]
    with connect_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM aggregation_versions").fetchone()[0] == 2
        archived = [json.loads(x[0]) for x in conn.execute("SELECT payload FROM source_snapshots")]
        assert any(x["toilets"] == before for x in archived)


def test_raw_payload_survives_failed_normalization(monkeypatch):
    initialize_db()
    payload = {
        "features": [
            {
                "properties": {"pid": "x", "untouched": "保留"},
                "geometry": {"coordinates": ["bad", 25]},
            }
        ]
    }
    fake = Mock()
    fake.get_toilets_by_area.return_value = payload
    monkeypatch.setattr(sync_moenv, "MoenvClient", lambda: fake)
    with pytest.raises(ValueError):
        sync_moenv.sync_moenv_data()
    with connect_db() as conn:
        saved = conn.execute(
            "SELECT payload FROM source_snapshots WHERE kind='government_payload'"
        ).fetchall()
        assert len(saved) == 2
        assert all(json.loads(x[0]) == payload for x in saved)
        assert conn.execute("SELECT COUNT(*) FROM toilets").fetchone()[0] == 2
    fake.close.assert_called_once()


def test_snapshot_content_is_deduplicated():
    initialize_db()
    with connect_db() as conn:
        initialize_archive(conn)
        a = preserve_snapshot(conn, "government_payload", {"raw": "original"}, "63000")
        b = preserve_snapshot(conn, "government_payload", {"raw": "original"}, "63000")
        assert a == b
        assert conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0] == 1


def test_archive_is_immutable_and_hours_changes_publish_new_version():
    import sqlite3

    seed(hospital_rows())
    first, _ = published_groups()
    with connect_db() as conn:
        for statement in (
            "UPDATE source_snapshots SET payload='{}'",
            "DELETE FROM source_snapshots",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                conn.execute(statement)
        conn.execute("INSERT INTO opening_hours VALUES('a',0,'09:00','18:00',0)")
    assert published_groups()[0] != first


def test_bbox_does_not_truncate_group_and_ids_survive_new_duplicate(client):
    seed([row("a")])
    first = client.get("/v1/toilets?aggregate=true").json()["items"][0]
    seed([row("a"), row("b", lat=25.0001)])
    # Only representative lies within this tiny viewport, but both sources survive.
    second = client.get(
        "/v1/toilets?aggregate=true&bbox=120.99999,24.99999,121.00001,25.00001"
    ).json()["items"][0]
    assert first["id"] == second["id"]
    assert len(second["sourceRecords"]) == 2


def test_known_open_and_closed_accessible_do_not_satisfy_combined_filter(client):
    seed(hospital_rows())
    with connect_db() as conn:
        for day in range(7):
            conn.execute("INSERT INTO opening_hours VALUES('a',?,'00:00','23:59',1)", (day,))
    assert client.get("/v1/toilets?aggregate=true&open_now=true").json()["total"] == 1
    assert (
        client.get("/v1/toilets?aggregate=true&open_now=true&toilet_types=accessible").json()[
            "items"
        ]
        == []
    )
