"""Versioned, lossless display groups; never deletes or rewrites source toilets."""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from math import asin, cos, radians, sin, sqrt

from app.core.db import connect_db
from app.models.schemas import ToiletMapItem

RULE_VERSION = "3"
MAX_GROUP_SPREAD_M = 150
# Reviewed facility identities. Address aliases are scoped to the name prefix.
FACILITIES = [
    {
        "id": "taipei-women-children-hospital",
        "name": "聯合醫院和平婦幼院區（婦幼）",
        "prefix": "聯合醫院和平婦幼院區(婦幼)",
        "city": "Taipei",
        "address": "臺北市中正區南福里福州街12號",
    },
    {
        "id": "guihou-fishermen-market",
        "name": "漁夫巿集",
        "prefix": "漁夫巿集-",
        "city": "New Taipei",
        "address": "新北市萬里區龜吼村漁澳16之6",
        "address_aliases": ["新北市萬里區龜吼村漁澳16之"],
        "allow_coordinate_spread": True,
    },
    {
        "id": "px-mart-tucheng-hypermarket",
        "name": "大全聯土城店",
        "prefix": "大全聯土城店",
        "city": "New Taipei",
        "address": "新北市土城區永寧里永安街25號",
        "allow_coordinate_spread": True,
    },
]

FLOOR_TOKEN = (
    r"(?:地下[一二三四五六七八九十\d]+樓|B\d{1,2}F|B[1-9]|[1-9]\d?F|[一二三四五六七八九十\d]+樓)"
)
BUILDING_TOKEN = r"(?:第[一二三四五六七八九十\d]+棟|[A-Z]棟)"
TOILET_TOKEN = r"(?:(?:性別友善|無障礙|親子|混合|男女|男|女)(?:廁所|廁)|公廁|廁所)"
BARE_TYPE = r"(?:性別友善|無障礙|親子|混合|男女|男|女)"
FACILITY_SUFFIX = re.compile(
    rf"(?:(?<![A-Za-z0-9]){FLOOR_TOKEN}|{BUILDING_TOKEN}|{TOILET_TOKEN}"
    rf"|[-_/ (]+{BARE_TYPE}|(?<=[樓F]){BARE_TYPE})[ )]*$",
    re.IGNORECASE,
)
STREET_NUMBER = re.compile(r"\d+(?:[-之]\d+)?號")


def normalized(value: str | None) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or ""))


def facility_name(value: str) -> str:
    name = unicodedata.normalize("NFKC", value.strip())
    while match := FACILITY_SUFFIX.search(name):
        shorter = name[: match.start()].rstrip(" -_/(")
        if not shorter or shorter.count("(") != shorter.count(")"):
            break
        name = shorter
    return name


def _hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def initialize_archive(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_snapshots (
            id TEXT PRIMARY KEY, captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            kind TEXT NOT NULL, area_id TEXT, payload TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS source_snapshots_no_update
        BEFORE UPDATE ON source_snapshots BEGIN
            SELECT RAISE(ABORT, 'Source snapshots are immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS source_snapshots_no_delete
        BEFORE DELETE ON source_snapshots BEGIN
            SELECT RAISE(ABORT, 'Source snapshots are immutable');
        END;
        CREATE TABLE IF NOT EXISTS source_imports (
            id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            snapshot_id TEXT NOT NULL REFERENCES source_snapshots(id)
        );
        CREATE TABLE IF NOT EXISTS aggregation_versions (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            rule_version TEXT NOT NULL, groups_json TEXT NOT NULL, report_json TEXT NOT NULL
        );
    """)

    conn.execute(
        "CREATE TABLE IF NOT EXISTS aggregation_revision "
        "(id INTEGER PRIMARY KEY, value INTEGER NOT NULL)"
    )
    conn.execute("INSERT OR IGNORE INTO aggregation_revision VALUES(1,0)")
    for table in ("toilets", "opening_hours"):
        for action in ("INSERT", "UPDATE", "DELETE"):
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS aggregation_{table}_{action}
                AFTER {action} ON {table} BEGIN
                UPDATE aggregation_revision SET value=value+1 WHERE id=1;
                END""")


def preserve_snapshot(conn, kind: str, payload, area_id: str | None = None) -> str:
    snapshot_id = _hash([kind, area_id, payload])
    conn.execute(
        "INSERT OR IGNORE INTO source_snapshots(id,kind,area_id,payload) VALUES(?,?,?,?)",
        (snapshot_id, kind, area_id, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
    )
    if kind == "government_payload":
        conn.execute("INSERT INTO source_imports(snapshot_id) VALUES(?)", (snapshot_id,))
    return snapshot_id


def _distance(a, b) -> float:
    lat1, lat2 = radians(a["lat"]), radians(b["lat"])
    value = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(radians(b["lng"] - a["lng"]) / 2) ** 2
    )
    return 12742000 * asin(sqrt(min(1, value)))


def build_groups(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    buckets = defaultdict(list)
    labels = {}
    reviewed_spread = set()
    for row in rows:
        name, address = normalized(row["name"]), normalized(row["address"])
        # Broad names with a locality-only address need a reviewed mapping.
        label = (
            facility_name(row["name"])
            if name and STREET_NUMBER.search(address)
            else row["name"] or ""
        )
        key = (
            "exact:" + _hash([row["city"], normalized(label), address])
            if name and address
            else f"single:{row['id']}"
        )
        for facility in FACILITIES:
            if (
                row["city"] == facility["city"]
                and address
                in {
                    normalized(x)
                    for x in [facility["address"], *facility.get("address_aliases", [])]
                }
                and name.startswith(normalized(facility["prefix"]))
            ):
                key, label = "facility:" + facility["id"], facility["name"]
                if facility.get("allow_coordinate_spread"):
                    reviewed_spread.add(key)
                break
        buckets[key].append(row)
        labels[key] = min(label, labels.get(key, label))
    groups, report = [], []
    for key, members in sorted(buckets.items()):
        members.sort(key=lambda x: x["id"])
        conflict = any(
            _distance(a, b) > MAX_GROUP_SPREAD_M
            for i, a in enumerate(members)
            for b in members[i + 1 :]
        )
        if conflict:
            report.append(
                {
                    "reason": "coordinate_spread",
                    "candidate": key,
                    "sourceIds": [x["id"] for x in members],
                    "mergedByReview": key in reviewed_spread,
                }
            )
        split = conflict and key not in reviewed_spread
        partitions = [[x] for x in members] if split else [members]
        for part in partitions:
            grouped = len(part) > 1
            facility = grouped and (
                key.startswith("facility:") or len({normalized(x["name"]) for x in part}) > 1
            )
            group_id = (
                "group-" + _hash(key)[:24]
                if not split and not key.startswith("single:")
                else part[0]["id"]
            )
            representative = part[0]
            if conflict and grouped:
                # Choose an actual source point with the most nearby members.
                def rank(row):
                    distances = [_distance(row, other) for other in part]
                    return (-sum(d <= MAX_GROUP_SPREAD_M for d in distances), sum(distances))

                representative = min(part, key=rank)
            groups.append(
                {
                    "id": group_id,
                    "name": labels[key] if facility else facility_name(part[0]["name"] or ""),
                    "kind": "facility" if facility else "identical" if grouped else "single",
                    "sourceIds": [x["id"] for x in part],
                    "representativeId": representative["id"],
                }
            )
    assert sorted(x for g in groups for x in g["sourceIds"]) == sorted(r["id"] for r in rows)
    return groups, report


def published_groups() -> tuple[str, list[dict]]:
    with connect_db() as conn:
        initialize_archive(conn)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        revision = str(
            conn.execute("SELECT value FROM aggregation_revision WHERE id=1").fetchone()[0]
        )
        rules = _hash([RULE_VERSION, FACILITIES, MAX_GROUP_SPREAD_M])
        meta = dict(conn.execute("SELECT key,value FROM app_meta WHERE key LIKE 'aggregation_%'"))
        if meta.get("aggregation_revision") == revision and meta.get("aggregation_rules") == rules:
            existing = conn.execute(
                "SELECT groups_json FROM aggregation_versions WHERE id=?",
                (meta.get("aggregation_version"),),
            ).fetchone()
            if existing:
                return meta["aggregation_version"], json.loads(existing["groups_json"])
        rows = [dict(x) for x in conn.execute("SELECT * FROM toilets ORDER BY id")]
        hours = [
            dict(x)
            for x in conn.execute("SELECT * FROM opening_hours ORDER BY toilet_id,day_of_week")
        ]
        payload = {"toilets": rows, "opening_hours": hours}
        version = _hash([rules, payload])
        for key, value in (("aggregation_revision", revision), ("aggregation_rules", rules)):
            conn.execute(
                "INSERT INTO app_meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        existing = conn.execute(
            "SELECT groups_json FROM aggregation_versions WHERE id=?", (version,)
        ).fetchone()
        if existing:
            conn.execute(
                "INSERT INTO app_meta(key,value) VALUES('aggregation_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (version,),
            )
            return version, json.loads(existing["groups_json"])
        # Existing imports cannot be reconstructed as raw payloads. Label this honestly.
        preserve_snapshot(conn, "normalized_database", payload)
        groups, report = build_groups(rows)
        rows_by_id = {row["id"]: row for row in rows}
        hours_by_id = defaultdict(list)
        for hour in hours:
            hours_by_id[hour["toilet_id"]].append(
                (hour["day_of_week"], hour["open_time"], hour["close_time"], hour["is_24h"])
            )
        for group in groups:
            if len(group["sourceIds"]) < 2:
                continue
            ids = group["sourceIds"]
            if len({tuple(hours_by_id[source_id]) for source_id in ids}) > 1:
                report.append({"reason": "different_hours", "groupId": group["id"]})
            members = [rows_by_id[source_id] for source_id in ids]
            if len({(r["toilet_types"], r["has_diaper_table"]) for r in members}) > 1:
                report.append({"reason": "different_facilities", "groupId": group["id"]})
        conn.execute(
            "INSERT OR IGNORE INTO aggregation_versions VALUES(?,CURRENT_TIMESTAMP,?,?,?)",
            (
                version,
                RULE_VERSION,
                json.dumps(groups, ensure_ascii=False),
                json.dumps(report, ensure_ascii=False),
            ),
        )
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('aggregation_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (version,),
        )
        return version, groups


def source_details(item: ToiletMapItem) -> ToiletMapItem:
    name = unicodedata.normalize("NFKC", item.name)
    building = re.search(BUILDING_TOKEN, name)
    floor = re.search(rf"(?<![A-Za-z0-9]){FLOOR_TOKEN}(?![0-9])", name, re.IGNORECASE)
    return item.model_copy(
        update={"building": building[0] if building else None, "floor": floor[0] if floor else None}
    )


def summarize(
    group: dict, members: list[ToiletMapItem], version: str, matching_ids: set[str]
) -> ToiletMapItem:
    members = sorted(members, key=lambda x: x.id)
    representative = next(x for x in members if x.id == group["representativeId"])
    symbol_sources = defaultdict(list)
    for item in members:
        symbols = set(item.toiletTypes) - {"male", "female", "mixed"}
        if item.hasMenToilet:
            symbols.add("male")
        if item.hasWomenToilet:
            symbols.add("female")
        if item.hasDiaperTable:
            symbols.add("diaper_table")
        for symbol in symbols:
            symbol_sources[symbol].append(item.id)
    statuses = [x.openNow for x in members]
    status = True if True in statuses else False if all(x is False for x in statuses) else None
    hours = {x.openLabel for x in members}
    sources = [source_details(x) for x in members]
    return representative.model_copy(
        update={
            "id": group["id"],
            "name": group["name"],
            "groupKind": group["kind"],
            "aggregationVersion": version,
            "sourceCount": len(members),
            "building": sources[0].building if len(sources) == 1 else None,
            "floor": sources[0].floor if len(sources) == 1 else None,
            "sourceRecords": sources,
            "matchingSourceIds": sorted(matching_ids.intersection(x.id for x in members)),
            "symbolSources": dict(symbol_sources),
            "toiletTypes": sorted({t for x in members for t in x.toiletTypes}),
            "hasMenToilet": any(x.hasMenToilet for x in members),
            "hasWomenToilet": any(x.hasWomenToilet for x in members),
            "hasDiaperTable": any(x.hasDiaperTable for x in members),
            "openNow": status,
            "openLabel": next(iter(hours)) if len(hours) == 1 else "Hours vary by toilet",
        }
    )


def aggregate_records(
    items: list[ToiletMapItem],
    matching_ids: set[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
):
    version, groups = published_groups()
    by_id = {x.id: x for x in items}
    matching_ids = set(by_id) if matching_ids is None else matching_ids
    if bbox:
        west, south, east, north = bbox
        groups = [
            g
            for g in groups
            if g["representativeId"] in by_id
            and west <= by_id[g["representativeId"]].lng <= east
            and south <= by_id[g["representativeId"]].lat <= north
        ]
    return [
        summarize(g, [by_id[x] for x in g["sourceIds"]], version, matching_ids)
        for g in groups
        if matching_ids.intersection(g["sourceIds"]) and all(x in by_id for x in g["sourceIds"])
    ]
