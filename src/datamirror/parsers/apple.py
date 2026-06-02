"""Parser for Apple privacy data exports."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from datamirror.db import insert_event, record_import

PLATFORM = "apple"


def _parse_appstore_csv(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (
                row.get("Item Description", "")
                or row.get("Title", "")
                or row.get("App Name", "")
                or "Unknown app"
            )
            ts = (
                row.get("Order Date", "")
                or row.get("Purchase Date", "")
                or row.get("Date", "")
                or ""
            )
            price = row.get("Item Total", row.get("Price", ""))
            developer = row.get("Seller", row.get("Developer", ""))

            body_parts = []
            if developer:
                body_parts.append(f"Developer: {developer}")
            if price:
                body_parts.append(f"Price: {price}")

            insert_event(
                db,
                platform=PLATFORM,
                category="purchase",
                timestamp=ts,
                title=title,
                body="; ".join(body_parts) if body_parts else None,
                raw_json=json.dumps(row),
            )
            count += 1
    return count


def _parse_account_json(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("activities", data.get("events", [data]))
    else:
        return 0

    for item in items:
        if not isinstance(item, dict):
            continue
        title = (
            item.get("title", "")
            or item.get("activity", "")
            or item.get("type", "Account activity")
        )
        ts = (
            item.get("timestamp", "")
            or item.get("date", "")
            or item.get("time", "")
            or ""
        )

        insert_event(
            db,
            platform=PLATFORM,
            category="login",
            timestamp=str(ts),
            title=str(title),
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def parse(path: Path, db: sqlite3.Connection) -> int:
    """Parse an Apple privacy data export and insert events into the database."""
    path = Path(path)
    count = 0

    if path.is_file():
        if path.suffix.lower() == ".csv":
            count = _parse_appstore_csv(path, db)
        elif path.suffix.lower() == ".json":
            count = _parse_account_json(path, db)
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
        db.commit()
        return count

    if not path.is_dir():
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=0)
        db.commit()
        return 0

    # Walk the directory looking for known file patterns
    for csv_file in path.rglob("*.csv"):
        name_lower = csv_file.name.lower()
        if "appstore" in name_lower or "purchase" in name_lower or "store" in name_lower:
            try:
                count += _parse_appstore_csv(csv_file, db)
            except (csv.Error, KeyError):
                continue

    for json_file in path.rglob("*.json"):
        name_lower = json_file.name.lower()
        if "account" in name_lower or "activity" in name_lower:
            try:
                count += _parse_account_json(json_file, db)
            except (json.JSONDecodeError, KeyError):
                continue

    db.commit()
    record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
    db.commit()
    return count
