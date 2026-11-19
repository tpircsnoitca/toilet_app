"""Validate the release checkpoint and compare new feeds with the last good import."""

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.ingestion.sync_moenv import TARGET_CITIES


def read_checkpoint(path: Path, after_import: int | None = None) -> dict:
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("SQLite foreign key check failed")

        meta = dict(db.execute("SELECT key, value FROM app_meta"))
        (revision,) = db.execute("SELECT value FROM aggregation_revision WHERE id = 1").fetchone()
        if meta.get("aggregation_revision") != str(revision):
            raise ValueError("Published aggregation does not match the current SQLite revision")
        aggregation = db.execute(
            "SELECT groups_json FROM aggregation_versions WHERE id = ?",
            (meta.get("aggregation_version"),),
        ).fetchone()
        groups = json.loads(aggregation[0]) if aggregation else []
        if not groups or any(not group.get("sourceIds") for group in groups):
            raise ValueError("Expected published facility groups with source records")

        (last_import,) = db.execute("SELECT MAX(id) FROM source_imports").fetchone()
        counts = {}
        for area_id, city in TARGET_CITIES.items():
            imports = db.execute(
                """
                SELECT s.payload FROM source_imports i
                JOIN source_snapshots s ON s.id = i.snapshot_id
                WHERE s.kind = 'government_payload' AND s.area_id = ? AND i.id > ?
                ORDER BY i.id DESC LIMIT ?
                """,
                (
                    area_id,
                    after_import if after_import is not None else 0,
                    2 if after_import is not None else 1,
                ),
            ).fetchall()
            if len(imports) != 1:
                raise ValueError(f"Expected one archived import for {city}, found {len(imports)}")
            features = json.loads(imports[0][0]).get("features")
            if not isinstance(features, list) or not features:
                raise ValueError(f"Empty or malformed MOENV feed for {city}")
            counts[area_id] = len(features)

    return {
        "last_import": last_import,
        "last_synced_at": meta["last_synced_at"],
        "aggregation_version": meta["aggregation_version"],
        "feed_counts": counts,
    }


def validate_sync(previous: dict, current: dict) -> None:
    prior_sync = datetime.fromisoformat(previous["last_synced_at"])
    new_sync = datetime.fromisoformat(current["last_synced_at"])
    now = datetime.now(timezone.utc)
    if new_sync <= prior_sync or not now - timedelta(hours=1) <= new_sync <= now:
        raise ValueError(f"Expected a fresh sync timestamp, got {new_sync.isoformat()}")
    for area_id, city in TARGET_CITIES.items():
        old_count = previous["feed_counts"][area_id]
        new_count = current["feed_counts"][area_id]
        if new_count * 10 < old_count * 9:
            raise ValueError(
                f"{city} feed fell below 90% of the last good import: {new_count}/{old_count}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text()) if args.previous else None
    try:
        state = read_checkpoint(args.database, previous["last_import"] if previous else None)
        if previous:
            validate_sync(previous, state)
        if args.backup:
            with (
                closing(
                    sqlite3.connect(f"{args.database.resolve().as_uri()}?mode=ro", uri=True)
                ) as src,
                closing(sqlite3.connect(args.backup)) as dst,
            ):
                src.backup(dst)
    except (ValueError, KeyError, sqlite3.Error) as exc:
        parser.exit(1, f"Checkpoint validation failed: {exc}\n")
    print(json.dumps(state))


if __name__ == "__main__":
    main()
