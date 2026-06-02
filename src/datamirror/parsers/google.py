"""Parser for Google Takeout exports."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from datamirror.db import insert_event, record_import

PLATFORM = "google"


def _parse_activity_json(data: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    for item in data:
        title = item.get("title", "")
        ts = item.get("time", "")
        url = None
        body = None

        if "subtitles" in item and item["subtitles"]:
            sub = item["subtitles"][0]
            body = sub.get("name", "")
            url = sub.get("url")

        # Determine category from header or title
        header = item.get("header", "").lower()
        if "search" in header or "search" in title.lower():
            category = "search"
        elif "youtube" in header:
            category = "watch"
        elif "chrome" in header:
            category = "browse"
        elif "maps" in header or "location" in header:
            category = "location"
        else:
            category = "browse"

        insert_event(
            db,
            platform=PLATFORM,
            category=category,
            timestamp=ts,
            title=title,
            body=body,
            url=url,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_youtube_history(data: list[dict], db: sqlite3.Connection, category: str) -> int:
    count = 0
    for item in data:
        title = item.get("title", "")
        ts = item.get("time", "")
        url = item.get("titleUrl", "")

        insert_event(
            db,
            platform=PLATFORM,
            category=category,
            timestamp=ts,
            title=title,
            url=url,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_chrome_history(data: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    browser_history = data if isinstance(data, list) else data.get("Browser History", [])
    for item in browser_history:
        title = item.get("title", "")
        ts = item.get("time", item.get("time_usec", ""))
        url = item.get("url", "")

        insert_event(
            db,
            platform=PLATFORM,
            category="browse",
            timestamp=str(ts),
            title=title,
            url=url,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_location_history(data: dict, db: sqlite3.Connection) -> int:
    count = 0
    records = data.get("locations", data.get("records", []))
    for item in records:
        lat = item.get("latitudeE7", item.get("latitude"))
        lng = item.get("longitudeE7", item.get("longitude"))
        ts = item.get("timestamp", item.get("timestampMs", ""))

        if lat and isinstance(lat, int) and abs(lat) > 1000:
            lat = lat / 1e7
        if lng and isinstance(lng, int) and abs(lng) > 1000:
            lng = lng / 1e7

        insert_event(
            db,
            platform=PLATFORM,
            category="location",
            timestamp=str(ts),
            title="Location record",
            latitude=float(lat) if lat else None,
            longitude=float(lng) if lng else None,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _load_json(path: Path) -> dict | list:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def _walk_directory(root: Path, db: sqlite3.Connection) -> int:
    count = 0

    # My Activity JSON files
    activity_dir = root / "My Activity"
    if activity_dir.exists():
        for json_file in activity_dir.rglob("*.json"):
            try:
                data = _load_json(json_file)
                if isinstance(data, list):
                    count += _parse_activity_json(data, db)
            except (json.JSONDecodeError, KeyError):
                continue

    # YouTube watch history
    yt_watch = root / "YouTube and YouTube Music" / "history" / "watch-history.json"
    if yt_watch.exists():
        try:
            data = _load_json(yt_watch)
            if isinstance(data, list):
                count += _parse_youtube_history(data, db, "watch")
        except (json.JSONDecodeError, KeyError):
            pass

    # YouTube search history
    yt_search = root / "YouTube and YouTube Music" / "history" / "search-history.json"
    if yt_search.exists():
        try:
            data = _load_json(yt_search)
            if isinstance(data, list):
                count += _parse_youtube_history(data, db, "search")
        except (json.JSONDecodeError, KeyError):
            pass

    # Chrome browser history
    chrome_history = root / "Chrome" / "BrowserHistory.json"
    if chrome_history.exists():
        try:
            data = _load_json(chrome_history)
            count += _parse_chrome_history(data, db)
        except (json.JSONDecodeError, KeyError):
            pass

    # Location History
    loc_records = root / "Location History" / "Records.json"
    if loc_records.exists():
        try:
            data = _load_json(loc_records)
            count += _parse_location_history(data, db)
        except (json.JSONDecodeError, KeyError):
            pass

    return count


def parse(path: Path, db: sqlite3.Connection) -> int:
    path = Path(path)
    count = 0

    if path.is_dir():
        count = _walk_directory(path, db)
    elif zipfile.is_zipfile(path):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmpdir)
            tmp_path = Path(tmpdir)
            # Takeout ZIPs sometimes have a top-level "Takeout" folder
            takeout_dir = tmp_path / "Takeout"
            root = takeout_dir if takeout_dir.exists() else tmp_path
            count = _walk_directory(root, db)
    else:
        # Try parsing as a single JSON file
        try:
            data = _load_json(path)
            if isinstance(data, list):
                count = _parse_activity_json(data, db)
            elif isinstance(data, dict):
                count = _parse_location_history(data, db)
        except (json.JSONDecodeError, KeyError):
            pass

    db.commit()
    record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
    db.commit()
    return count
