import os
import sqlite3
from pathlib import Path


def _default_db_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / "toilets.db"


DB_PATH = Path(os.getenv("TOILET_DB_PATH", _default_db_path()))


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
