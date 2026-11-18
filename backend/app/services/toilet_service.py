import json
import re
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from app.core.db import connect_db
from app.models.schemas import GenderFilter, ToiletMapItem

_DB_INITIALIZED = False
FLOOR_TOKEN_PATTERN = re.compile(r"(?:B\d+|\d+F|[地上地下]\d+樓|\d+樓)")
GENDER_TOKEN_PATTERN = re.compile(
    r"(無障礙廁所|無障礙|性別友善廁所|性別友善|親子廁所|親子廁|男廁所|女廁所|男廁|女廁|男女廁|男女|男|女)"
)
TOILET_NUMBER_PATTERN = re.compile(r"(\d+號|\d{3,})")
_SAMPLE_TOILETS: list[dict[str, Any]] = [
    {
        "id": "tp_001",
        "name": "Taipei Main Station Public Toilet",
        "city": "Taipei",
        "district": "Zhongzheng",
        "address": "No. 3, Beiping W Rd",
        "lat": 25.0478,
        "lng": 121.5170,
        "toiletTypes": ["male", "female", "accessible"],
        "hasMenToilet": True,
        "hasWomenToilet": True,
        "hasDiaperTable": True,
        "openNow": True,
        "openLabel": "Open 24 hours",
    },
    {
        "id": "ntpc_001",
        "name": "Banqiao Station Public Toilet",
        "city": "New Taipei",
        "district": "Banqiao",
        "address": "No. 7, Sec. 2, Xianmin Blvd",
        "lat": 25.0142,
        "lng": 121.4635,
        "toiletTypes": ["male", "female", "family"],
        "hasMenToilet": True,
        "hasWomenToilet": True,
        "hasDiaperTable": True,
        "openNow": True,
        "openLabel": "Open until 23:00",
    },
]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    r = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return int(r * c)


def initialize_db() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return

    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS toilets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                district TEXT NOT NULL,
                address TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                toilet_types TEXT NOT NULL,
                has_men_toilet INTEGER NOT NULL DEFAULT 0,
                has_women_toilet INTEGER NOT NULL DEFAULT 0,
                has_diaper_table INTEGER NOT NULL DEFAULT 0,
                open_now INTEGER,
                open_label TEXT NOT NULL DEFAULT 'Hours unavailable'
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(toilets)").fetchall()}
        if "has_men_toilet" not in columns:
            conn.execute("ALTER TABLE toilets ADD COLUMN has_men_toilet INTEGER NOT NULL DEFAULT 0")
        if "has_women_toilet" not in columns:
            conn.execute(
                "ALTER TABLE toilets ADD COLUMN has_women_toilet INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opening_hours (
                toilet_id TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                open_time TEXT NOT NULL,
                close_time TEXT NOT NULL,
                is_24h INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (toilet_id, day_of_week),
                FOREIGN KEY (toilet_id) REFERENCES toilets (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) AS count FROM toilets").fetchone()["count"]

        if count == 0:
            for toilet in _SAMPLE_TOILETS:
                conn.execute(
                    """
                    INSERT INTO toilets (
                        id, name, city, district, address, lat, lng, toilet_types,
                        has_men_toilet, has_women_toilet, has_diaper_table, open_now, open_label
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        toilet["id"],
                        toilet["name"],
                        toilet["city"],
                        toilet["district"],
                        toilet["address"],
                        toilet["lat"],
                        toilet["lng"],
                        json.dumps([x.lower() for x in toilet["toiletTypes"]]),
                        int(bool(toilet["hasMenToilet"])),
                        int(bool(toilet["hasWomenToilet"])),
                        int(bool(toilet["hasDiaperTable"])),
                        int(toilet["openNow"]) if toilet["openNow"] is not None else None,
                        toilet["openLabel"],
                    ),
                )
                for day in range(7):
                    conn.execute(
                        """
                        INSERT INTO opening_hours (
                            toilet_id, day_of_week, open_time, close_time, is_24h
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (toilet["id"], day, "00:00", "23:59", 1),
                    )

    _DB_INITIALIZED = True


def _local_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Taipei"))


def _hours_query(now: datetime) -> str:
    # The weekday comes from the server clock, never from request input.
    day = now.weekday()
    return f"""
        SELECT toilets.*, today.open_time AS today_open, today.close_time AS today_close,
               today.is_24h AS today_24h, yesterday.open_time AS yesterday_open,
               yesterday.close_time AS yesterday_close, yesterday.is_24h AS yesterday_24h
        FROM toilets
        LEFT JOIN opening_hours AS today
          ON today.toilet_id = toilets.id AND today.day_of_week = {day}
        LEFT JOIN opening_hours AS yesterday
          ON yesterday.toilet_id = toilets.id AND yesterday.day_of_week = {(day - 1) % 7}
    """


def _opening_status(row: Any, now: datetime) -> tuple[Optional[bool], str]:
    def minutes(value: Optional[str]) -> Optional[int]:
        if not value or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            return None
        hour, minute = value.split(":")
        return int(hour) * 60 + int(minute)

    current = now.hour * 60 + now.minute
    start, end = minutes(row["today_open"]), minutes(row["today_close"])
    previous_start = minutes(row["yesterday_open"])
    previous_end = minutes(row["yesterday_close"])
    overnight_open = (
        not row["yesterday_24h"]
        and previous_start is not None
        and previous_end is not None
        and previous_start > previous_end
        and current < previous_end
    )
    if row["today_24h"]:
        return True, "Open 24 hours"
    # Ingestion historically substitutes the start for missing closing times.
    # Equal times therefore cannot safely mean either closed or open all day.
    if start is None or end is None or start == end:
        return (True if overnight_open else None), "Hours unavailable"
    label = f"{row['today_open']}–{row['today_close']}"
    if start > end:
        label += " (next day)"
        return overnight_open or current >= start, label
    return overnight_open or start <= current < end, label


def _row_to_toilet(row: Any, now: datetime) -> ToiletMapItem:
    open_now, open_label = _opening_status(row, now)
    return ToiletMapItem(
        id=row["id"],
        name=row["name"],
        city=row["city"],
        district=row["district"],
        address=row["address"],
        lat=row["lat"],
        lng=row["lng"],
        toiletTypes=json.loads(row["toilet_types"]),
        hasMenToilet=bool(row["has_men_toilet"]),
        hasWomenToilet=bool(row["has_women_toilet"]),
        hasDiaperTable=bool(row["has_diaper_table"]),
        openNow=open_now,
        openLabel=open_label,
    )


def _polish_toilet_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return text

    # Remove common floor/level markers and standalone gender labels.
    text = FLOOR_TOKEN_PATTERN.sub("", text)
    text = GENDER_TOKEN_PATTERN.sub("", text)
    text = TOILET_NUMBER_PATTERN.sub("", text)
    text = re.sub(r"[()（）\[\]]", "", text)
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text or name


def list_toilets(
    bbox: Optional[tuple[float, float, float, float]] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    keyword: Optional[str] = None,
    open_now: Optional[bool] = None,
    has_men_toilet: Optional[bool] = None,
    has_women_toilet: Optional[bool] = None,
    has_diaper_table: Optional[bool] = None,
    toilet_type: Optional[str] = None,
    toilet_types: Optional[list[str]] = None,
    gender: Optional[list[GenderFilter]] = None,
) -> List[ToiletMapItem]:
    initialize_db()

    now = _local_now()
    query = _hours_query(now) + " WHERE 1=1"
    params: list[Any] = []

    if bbox:
        min_lng, min_lat, max_lng, max_lat = bbox
        query += " AND lng >= ? AND lng <= ? AND lat >= ? AND lat <= ?"
        params.extend([min_lng, max_lng, min_lat, max_lat])

    if city:
        query += " AND lower(replace(city, ' ', '_')) = ?"
        params.append(city.lower().strip())

    if district:
        query += " AND lower(district) = ?"
        params.append(district.lower().strip())

    if keyword:
        query += " AND (lower(name) LIKE ? OR lower(ifnull(address, '')) LIKE ?)"
        keyword_l = f"%{keyword.lower().strip()}%"
        params.extend([keyword_l, keyword_l])

    if has_men_toilet is not None:
        query += " AND has_men_toilet = ?"
        params.append(int(has_men_toilet))

    if has_women_toilet is not None:
        query += " AND has_women_toilet = ?"
        params.append(int(has_women_toilet))

    if has_diaper_table is not None:
        query += " AND has_diaper_table = ?"
        params.append(int(has_diaper_table))

    if toilet_type:
        query += " AND lower(toilet_types) LIKE ?"
        params.append(f'%"{toilet_type.lower().strip()}"%')

    with connect_db() as conn:
        rows = conn.execute(query, params).fetchall()

    items = [_row_to_toilet(row, now) for row in rows]
    if toilet_types:
        required = {value.lower().strip() for value in toilet_types}
        items = [item for item in items if required.issubset(item.toiletTypes)]
    if gender:
        items = [
            item
            for item in items
            if ("men" in gender and item.hasMenToilet)
            or ("women" in gender and item.hasWomenToilet)
            or ("gender_friendly" in gender and "gender_friendly" in item.toiletTypes)
        ]
    if open_now is not None:
        items = [item for item in items if item.openNow is open_now]
    return items


def nearby_toilets(
    lat: float,
    lng: float,
    radius_m: int = 1000,
    city: Optional[str] = None,
    district: Optional[str] = None,
    keyword: Optional[str] = None,
    open_now: Optional[bool] = None,
    has_men_toilet: Optional[bool] = None,
    has_women_toilet: Optional[bool] = None,
    has_diaper_table: Optional[bool] = None,
    toilet_type: Optional[str] = None,
    toilet_types: Optional[list[str]] = None,
    gender: Optional[list[GenderFilter]] = None,
) -> List[ToiletMapItem]:
    base = list_toilets(
        city=city,
        district=district,
        keyword=keyword,
        open_now=open_now,
        has_men_toilet=has_men_toilet,
        has_women_toilet=has_women_toilet,
        has_diaper_table=has_diaper_table,
        toilet_type=toilet_type,
        toilet_types=toilet_types,
        gender=gender,
    )

    with_distance = []
    for t in base:
        d = _haversine_m(lat, lng, t.lat, t.lng)
        if d <= radius_m:
            with_distance.append(t.model_copy(update={"distanceM": d}))

    return sorted(with_distance, key=lambda x: x.distanceM or 0)


def get_toilet(toilet_id: str) -> Optional[ToiletMapItem]:
    initialize_db()
    now = _local_now()
    with connect_db() as conn:
        row = conn.execute(_hours_query(now) + " WHERE toilets.id = ?", (toilet_id,)).fetchone()
    if row is None:
        return None
    return _row_to_toilet(row, now)


def get_opening_hours(toilet_id: str) -> list[dict[str, Any]]:
    initialize_db()
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT day_of_week, open_time, close_time, is_24h
            FROM opening_hours
            WHERE toilet_id = ?
            ORDER BY day_of_week ASC
            """,
            (toilet_id,),
        ).fetchall()

    return [
        {
            "dayOfWeek": row["day_of_week"],
            "openTime": row["open_time"],
            "closeTime": row["close_time"],
            "is24h": bool(row["is_24h"]),
        }
        for row in rows
    ]


def get_last_synced_at() -> str | None:
    initialize_db()
    with connect_db() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key = 'last_synced_at'").fetchone()
    if row is None:
        return None
    return str(row["value"])


def list_districts(city: Optional[str] = None) -> list[str]:
    initialize_db()
    query = "SELECT DISTINCT district FROM toilets WHERE district <> ''"
    params: list[Any] = []
    if city:
        query += " AND lower(replace(city, ' ', '_')) = ?"
        params.append(city.lower().strip())
    query += " ORDER BY district ASC"

    with connect_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [str(row["district"]) for row in rows]


def aggregate_toilets(
    items: List[ToiletMapItem], bbox: Optional[tuple[float, float, float, float]] = None
) -> List[ToiletMapItem]:
    from app.services.aggregation import aggregate_records

    return aggregate_records(list_toilets(), {x.id for x in items}, bbox=bbox)
