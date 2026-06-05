"""SQLite database setup and query helpers for datamirror."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".datamirror" / "datamirror.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    category TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    url TEXT,
    latitude REAL,
    longitude REAL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_platform_ts ON events (platform, timestamp);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    source_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    event_count INTEGER NOT NULL
);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure the schema exists."""
    path = db_path if db_path is not None else DEFAULT_DB_PATH
    if str(path) == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def insert_event(
    db: sqlite3.Connection,
    *,
    platform: str,
    category: str,
    timestamp: str,
    title: str,
    body: str | None = None,
    url: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    raw_json: str | None = None,
) -> None:
    db.execute(
        """INSERT INTO events
           (platform, category, timestamp, title, body, url, latitude, longitude, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (platform, category, timestamp, title, body, url, latitude, longitude, raw_json),
    )


def insert_profile(
    db: sqlite3.Connection,
    *,
    platform: str,
    category: str,
    key: str,
    value: str,
) -> None:
    """Insert a profile/ad-interest row."""
    db.execute(
        "INSERT INTO profiles (platform, category, key, value) VALUES (?, ?, ?, ?)",
        (platform, category, key, value),
    )


def record_import(
    db: sqlite3.Connection,
    *,
    platform: str,
    source_path: str,
    event_count: int,
) -> None:
    """Record a completed import in the imports table."""
    db.execute(
        "INSERT INTO imports (platform, source_path, imported_at, event_count) VALUES (?, ?, ?, ?)",
        (platform, source_path, datetime.utcnow().isoformat(), event_count),
    )


def query_timeline(
    db: sqlite3.Connection,
    *,
    platform: str | None = None,
    category: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if platform:
        clauses.append("platform = ?")
        params.append(platform)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if after:
        clauses.append("timestamp >= ?")
        params.append(after)
    if before:
        clauses.append("timestamp <= ?")
        params.append(before)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_stats(db: sqlite3.Connection) -> dict[str, Any]:
    """Return per-platform event counts, date ranges, and category breakdowns."""
    stats: dict[str, Any] = {"platforms": {}, "total_events": 0}

    rows = db.execute(
        """SELECT platform, COUNT(*) as cnt,
                  MIN(timestamp) as earliest,
                  MAX(timestamp) as latest
           FROM events GROUP BY platform"""
    ).fetchall()

    for row in rows:
        platform = row["platform"]
        cat_rows = db.execute(
            "SELECT category, COUNT(*) as cnt FROM events WHERE platform = ? GROUP BY category",
            (platform,),
        ).fetchall()
        categories = {r["category"]: r["cnt"] for r in cat_rows}
        stats["platforms"][platform] = {
            "count": row["cnt"],
            "earliest": row["earliest"],
            "latest": row["latest"],
            "categories": categories,
        }
        stats["total_events"] += row["cnt"]

    return stats


def count_events(db: sqlite3.Connection) -> int:
    """Return total event count."""
    row = db.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
    return row["cnt"]


def search_events(
    db: sqlite3.Connection,
    *,
    query: str,
    platform: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Full text search across event titles and bodies."""
    clauses: list[str] = ["(title LIKE ? OR body LIKE ?)"]
    pattern = f"%{query}%"
    params: list[Any] = [pattern, pattern]

    if platform:
        clauses.append("platform = ?")
        params.append(platform)
    if category:
        clauses.append("category = ?")
        params.append(category)

    where = "WHERE " + " AND ".join(clauses)
    sql = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def export_events(
    db: sqlite3.Connection,
    *,
    platform: str | None = None,
    category: str | None = None,
    after: str | None = None,
    before: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if platform:
        clauses.append("platform = ?")
        params.append(platform)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if after:
        clauses.append("timestamp >= ?")
        params.append(after)
    if before:
        clauses.append("timestamp <= ?")
        params.append(before)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"SELECT * FROM events {where} ORDER BY timestamp DESC"
    rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_import_history(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM imports ORDER BY imported_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def delete_events(
    db: sqlite3.Connection,
    *,
    platform: str | None = None,
    category: str | None = None,
    before: str | None = None,
) -> int:
    """Delete events matching the given filters. Returns the number of rows removed."""
    clauses: list[str] = []
    params: list[Any] = []

    if platform:
        clauses.append("platform = ?")
        params.append(platform)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if before:
        clauses.append("timestamp <= ?")
        params.append(before)

    if not clauses:
        return 0

    where = "WHERE " + " AND ".join(clauses)
    cursor = db.execute(f"DELETE FROM events {where}", params)
    db.commit()
    return cursor.rowcount
