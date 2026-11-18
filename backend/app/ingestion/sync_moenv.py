import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.db import connect_db
from app.ingestion.moenv_client import MoenvClient
from app.services.aggregation import initialize_archive, preserve_snapshot, published_groups
from app.services.toilet_service import initialize_db

TARGET_CITIES = {
    "63000": "Taipei",
    "10001": "New Taipei",
}

TOILET_TYPE_MAP = {
    "1": "male",
    "2": "female",
    "3": "family",
    "4": "accessible",
    "5": "mixed",
    "6": "gender_friendly",
}

DAY_FIELDS = [
    ("MonStart", "MonEnd"),
    ("TueStart", "TueEnd"),
    ("WedStart", "WedEnd"),
    ("ThuStart", "ThuEnd"),
    ("FriStart", "FriEnd"),
    ("SatStart", "SatEnd"),
    ("SunStart", "SunEnd"),
]

TIME_PATTERN = re.compile(r"(\d{1,2})[:：](\d{2})")
DISTRICT_PATTERN = re.compile(r"^(?:臺北市|台北市|新北市)([^區鄉鎮市]{1,6}[區鄉鎮市])")


def _parse_hhmm(text: str) -> str | None:
    match = TIME_PATTERN.search(text or "")
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _extract_district(address: str) -> str:
    match = DISTRICT_PATTERN.search(address or "")
    if match:
        return match.group(1)
    return ""


def _compute_open_label(props: dict[str, Any]) -> str:
    starts = [str(props.get(day_start, "")).strip() for day_start, _ in DAY_FIELDS]
    non_empty = [value for value in starts if value]
    if non_empty and all("全天開放" in value for value in non_empty):
        return "Open 24 hours"
    return "Hours available"


def _infer_gender_flags(toilet_type_code: str, toilet_name: str) -> tuple[bool, bool]:
    has_men = toilet_type_code == "1"
    has_women = toilet_type_code == "2"

    # Mixed toilets are usually available for all genders.
    if toilet_type_code == "5":
        has_men = True
        has_women = True

    # Name-level hints improve accuracy for records with noisy type values.
    if "男" in toilet_name:
        has_men = True
    if "女" in toilet_name:
        has_women = True

    return has_men, has_women


def _normalize_feature(feature: dict[str, Any], city_name: str) -> dict[str, Any] | None:
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coordinates = geometry.get("coordinates", [])
    if len(coordinates) != 2:
        return None

    toilet_id = str(props.get("pid") or props.get("ToiletID") or "").strip()
    if not toilet_id:
        return None

    lat = float(coordinates[1])
    lng = float(coordinates[0])
    address = str(props.get("ctrl_addr") or "").strip()
    toilet_type_code = str(props.get("toilet_type") or "").strip()
    toilet_name = str(props.get("ctrl_name") or "").strip()
    toilet_types = (
        [TOILET_TYPE_MAP[toilet_type_code]] if toilet_type_code in TOILET_TYPE_MAP else []
    )
    has_men_toilet, has_women_toilet = _infer_gender_flags(toilet_type_code, toilet_name)

    opening_hours = []
    for day_of_week, (start_field, end_field) in enumerate(DAY_FIELDS):
        raw_start = str(props.get(start_field, "")).strip()
        raw_end = str(props.get(end_field, "")).strip()
        is_24h = "全天開放" in raw_start
        open_time = "00:00" if is_24h else (_parse_hhmm(raw_start) or "00:00")
        close_time = "23:59" if is_24h else (_parse_hhmm(raw_end) or open_time)

        opening_hours.append(
            {
                "day_of_week": day_of_week,
                "open_time": open_time,
                "close_time": close_time,
                "is_24h": 1 if is_24h else 0,
            }
        )

    return {
        "id": toilet_id,
        "name": toilet_name,
        "city": city_name,
        "district": _extract_district(address),
        "address": address,
        "lat": lat,
        "lng": lng,
        "toilet_types": toilet_types,
        "has_men_toilet": 1 if has_men_toilet else 0,
        "has_women_toilet": 1 if has_women_toilet else 0,
        "has_diaper_table": 1 if str(props.get("Equipment", "")).strip() == "1" else 0,
        "open_now": 1 if _compute_open_label(props) == "Open 24 hours" else None,
        "open_label": _compute_open_label(props),
        "opening_hours": opening_hours,
    }


def _upsert_toilet(conn: sqlite3.Connection, toilet: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO toilets (
            id, name, city, district, address, lat, lng, toilet_types,
            has_men_toilet, has_women_toilet, has_diaper_table, open_now, open_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            city = excluded.city,
            district = excluded.district,
            address = excluded.address,
            lat = excluded.lat,
            lng = excluded.lng,
            toilet_types = excluded.toilet_types,
            has_men_toilet = excluded.has_men_toilet,
            has_women_toilet = excluded.has_women_toilet,
            has_diaper_table = excluded.has_diaper_table,
            open_now = excluded.open_now,
            open_label = excluded.open_label
        """,
        (
            toilet["id"],
            toilet["name"],
            toilet["city"],
            toilet["district"],
            toilet["address"],
            toilet["lat"],
            toilet["lng"],
            json.dumps(toilet["toilet_types"]),
            toilet["has_men_toilet"],
            toilet["has_women_toilet"],
            toilet["has_diaper_table"],
            toilet["open_now"],
            toilet["open_label"],
        ),
    )

    conn.execute("DELETE FROM opening_hours WHERE toilet_id = ?", (toilet["id"],))
    for slot in toilet["opening_hours"]:
        conn.execute(
            """
            INSERT INTO opening_hours (toilet_id, day_of_week, open_time, close_time, is_24h)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                toilet["id"],
                slot["day_of_week"],
                slot["open_time"],
                slot["close_time"],
                slot["is_24h"],
            ),
        )


def sync_moenv_data() -> dict[str, int | str]:
    initialize_db()
    client = MoenvClient()
    inserted_or_updated = 0

    try:
        # Persist complete decoded source responses before normalization. Even a
        # failed normalization/import leaves its input available for diagnosis.
        payloads = {}
        for area_id in TARGET_CITIES:
            payload = client.get_toilets_by_area(area_id)
            with connect_db() as archive:
                initialize_archive(archive)
                preserve_snapshot(archive, "government_payload", payload, area_id)
            payloads[area_id] = payload
        # Archive the current normalized state before any source updates.
        published_groups()
        with connect_db() as conn:
            # Remove bootstrap sample rows so API reflects official data only.
            conn.execute("DELETE FROM toilets WHERE id IN ('tp_001', 'ntpc_001')")
            for area_id, city_name in TARGET_CITIES.items():
                payload = payloads[area_id]
                for feature in payload.get("features", []):
                    normalized = _normalize_feature(feature, city_name)
                    if not normalized:
                        continue
                    _upsert_toilet(conn, normalized)
                    inserted_or_updated += 1

            synced_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO app_meta (key, value)
                VALUES ('last_synced_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (synced_at,),
            )

        version, groups = published_groups()
        return {
            "syncedAt": synced_at,
            "recordsUpserted": inserted_or_updated,
            "aggregationVersion": version,
            "displayGroups": len(groups),
        }
    finally:
        client.close()


if __name__ == "__main__":
    result = sync_moenv_data()
    print(f"Synced at {result['syncedAt']}, records upserted: {result['recordsUpserted']}")
