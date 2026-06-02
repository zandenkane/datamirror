"""Parser for Meta (Facebook/Instagram) data exports."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from datamirror.db import insert_event, insert_profile, record_import

PLATFORM = "meta"


def _fix_encoding(text: str) -> str:
    """Fix Facebook's Latin-1 encoded UTF-8 strings.

    Facebook exports encode UTF-8 text as Latin-1, so special characters
    appear garbled. This re-encodes the string properly.
    """
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def _load_json(path: Path) -> dict | list:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _ts_to_iso(ts: int | float) -> str:
    return datetime.utcfromtimestamp(ts).isoformat()


def _ts_ms_to_iso(ts_ms: int | float) -> str:
    return datetime.utcfromtimestamp(ts_ms / 1000).isoformat()


def _parse_posts(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    data = _load_json(path)
    if not isinstance(data, list):
        return 0

    for post in data:
        ts = post.get("timestamp", 0)
        title = _fix_encoding(post.get("title", "Post"))

        body_parts = []
        for d in post.get("data", []):
            if "post" in d:
                body_parts.append(_fix_encoding(d["post"]))
        body = "\n".join(body_parts) if body_parts else None

        insert_event(
            db,
            platform=PLATFORM,
            category="post",
            timestamp=_ts_to_iso(ts),
            title=title,
            body=body,
            raw_json=json.dumps(post),
        )
        count += 1
    return count


def _parse_messages(root: Path, db: sqlite3.Connection) -> int:
    count = 0
    inbox = root / "messages" / "inbox"
    if not inbox.exists():
        return 0

    for conv_dir in inbox.iterdir():
        if not conv_dir.is_dir():
            continue
        msg_file = conv_dir / "message_1.json"
        if not msg_file.exists():
            continue

        try:
            data = _load_json(msg_file)
        except (json.JSONDecodeError, KeyError):
            continue

        participants = data.get("participants", [])
        participant_names = ", ".join(
            _fix_encoding(p.get("name", "Unknown")) for p in participants
        )

        for msg in data.get("messages", []):
            sender = _fix_encoding(msg.get("sender_name", "Unknown"))
            ts_ms = msg.get("timestamp_ms", 0)
            content = msg.get("content", "")
            if content:
                content = _fix_encoding(content)

            insert_event(
                db,
                platform=PLATFORM,
                category="message",
                timestamp=_ts_ms_to_iso(ts_ms),
                title=f"Message from {sender} in {participant_names}",
                body=content,
                raw_json=json.dumps(msg),
            )
            count += 1

    return count


def _parse_comments(path: Path, db: sqlite3.Connection) -> int:
    count = 0
    data = _load_json(path)

    comments = data if isinstance(data, list) else data.get("comments_v2", data.get("comments", []))
    if not isinstance(comments, list):
        return 0

    for comment in comments:
        ts = comment.get("timestamp", 0)
        title = _fix_encoding(comment.get("title", "Comment"))

        body = None
        for d in comment.get("data", []):
            if "comment" in d:
                body = _fix_encoding(d["comment"].get("comment", ""))
                break

        insert_event(
            db,
            platform=PLATFORM,
            category="comment",
            timestamp=_ts_to_iso(ts),
            title=title,
            body=body,
            raw_json=json.dumps(comment),
        )
        count += 1
    return count


def _parse_profile(path: Path, db: sqlite3.Connection) -> int:
    data = _load_json(path)
    profile = data.get("profile_v2", data) if isinstance(data, dict) else {}
    count = 0

    for key, value in profile.items():
        if isinstance(value, str):
            insert_profile(
                db,
                platform=PLATFORM,
                category="demographic",
                key=key,
                value=_fix_encoding(value),
            )
            count += 1

    return count


def parse(path: Path, db: sqlite3.Connection) -> int:
    """Parse a Meta (Facebook) data export directory and insert events into the database."""
    path = Path(path)
    count = 0

    if not path.is_dir():
        # Try parsing as a single JSON file (e.g. your_posts_1.json directly)
        try:
            data = _load_json(path)
            if isinstance(data, list):
                for post in data:
                    ts = post.get("timestamp", 0)
                    title = _fix_encoding(post.get("title", "Post"))

                    body_parts = []
                    for d in post.get("data", []):
                        if "post" in d:
                            body_parts.append(_fix_encoding(d["post"]))
                    body = "\n".join(body_parts) if body_parts else None

                    insert_event(
                        db,
                        platform=PLATFORM,
                        category="post",
                        timestamp=_ts_to_iso(ts),
                        title=title,
                        body=body,
                        raw_json=json.dumps(post),
                    )
                    count += 1
        except (json.JSONDecodeError, KeyError):
            pass
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
        db.commit()
        return count

    # Posts
    posts_file = path / "posts" / "your_posts_1.json"
    if posts_file.exists():
        try:
            count += _parse_posts(posts_file, db)
        except (json.JSONDecodeError, KeyError):
            pass

    # Messages
    count += _parse_messages(path, db)

    # Comments
    comments_file = path / "comments" / "comments.json"
    if comments_file.exists():
        try:
            count += _parse_comments(comments_file, db)
        except (json.JSONDecodeError, KeyError):
            pass

    # Profile
    profile_file = path / "profile_information" / "profile_information.json"
    if profile_file.exists():
        try:
            _parse_profile(profile_file, db)
        except (json.JSONDecodeError, KeyError):
            pass

    db.commit()
    record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
    db.commit()
    return count
