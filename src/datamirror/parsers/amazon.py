"""Parser for Amazon data exports."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from datamirror.db import insert_event, record_import

PLATFORM = "amazon"


def _parse_order_csv(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Amazon CSVs use various column naming conventions
            order_date = (
                row.get("Order Date", "")
                or row.get("order_date", "")
                or row.get("OrderDate", "")
            )
            title = (
                row.get("Title", "")
                or row.get("Product Name", "")
                or row.get("title", "")
                or "Unknown item"
            )
            order_id = row.get("Order ID", row.get("order_id", ""))
            category = row.get("Category", row.get("category", ""))
            quantity = row.get("Quantity", row.get("quantity", ""))
            price = (
                row.get("Purchase Price Per Unit", "")
                or row.get("Item Total", "")
                or row.get("price", "")
            )

            body_parts = []
            if order_id:
                body_parts.append(f"Order: {order_id}")
            if category:
                body_parts.append(f"Category: {category}")
            if quantity:
                body_parts.append(f"Quantity: {quantity}")
            if price:
                body_parts.append(f"Price: {price}")

            insert_event(
                db,
                platform=PLATFORM,
                category="purchase",
                timestamp=order_date,
                title=title,
                body="; ".join(body_parts) if body_parts else None,
                raw_json=json.dumps(row),
            )
            count += 1
    return count


def _parse_search_csv(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = (
                row.get("Search Query", "")
                or row.get("First Search Query", "")
                or row.get("query", "")
                or ""
            )
            ts = (
                row.get("Search Date", "")
                or row.get("Timestamp", "")
                or row.get("timestamp", "")
                or ""
            )

            if query:
                insert_event(
                    db,
                    platform=PLATFORM,
                    category="search",
                    timestamp=ts,
                    title=f"Search: {query}",
                    raw_json=json.dumps(row),
                )
                count += 1
    return count


def parse(path: Path, db: sqlite3.Connection) -> int:
    """Parse an Amazon data export directory and insert events into the database."""
    path = Path(path)
    count = 0

    if path.is_file() and path.suffix.lower() == ".csv":
        # Single CSV file passed directly
        count = _parse_order_csv(path, db)
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
        db.commit()
        return count

    if not path.is_dir():
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=0)
        db.commit()
        return 0

    # Look for order history CSVs in Retail.OrderHistory.1/ or similar
    for csv_dir in path.iterdir():
        if csv_dir.is_dir() and "orderhistory" in csv_dir.name.lower().replace(".", ""):
            for csv_file in csv_dir.glob("*.csv"):
                try:
                    count += _parse_order_csv(csv_file, db)
                except (csv.Error, KeyError):
                    continue

    # Also check for CSVs directly in the root
    for csv_file in path.glob("*.csv"):
        if "order" in csv_file.name.lower():
            try:
                count += _parse_order_csv(csv_file, db)
            except (csv.Error, KeyError):
                continue

    # Search history
    search_dir = path / "Search-Data"
    if search_dir.exists():
        for csv_file in search_dir.glob("*.csv"):
            try:
                count += _parse_search_csv(csv_file, db)
            except (csv.Error, KeyError):
                continue

    db.commit()
    record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
    db.commit()
    return count
