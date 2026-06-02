"""Parser for TikTok data exports."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from datamirror.db import insert_event, insert_profile, record_import

PLATFORM = "tiktok"


def _parse_video_history(items: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        title = item.get("VideoLink", item.get("Link", "Video"))
        ts = item.get("Date", item.get("date", ""))

        insert_event(
            db,
            platform=PLATFORM,
            category="watch",
            timestamp=ts,
            title="Watched video",
            url=title if title.startswith("http") else None,
            body=title if not title.startswith("http") else None,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_like_list(items: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        link = item.get("VideoLink", item.get("Link", ""))
        ts = item.get("Date", item.get("date", ""))

        insert_event(
            db,
            platform=PLATFORM,
            category="browse",
            timestamp=ts,
            title="Liked video",
            url=link if link.startswith("http") else None,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_comments(items: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        comment_text = item.get("Comment", item.get("comment", ""))
        ts = item.get("Date", item.get("date", ""))

        insert_event(
            db,
            platform=PLATFORM,
            category="comment",
            timestamp=ts,
            title="Comment",
            body=comment_text,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_favorites(items: list[dict], db: sqlite3.Connection) -> int:
    count = 0
    for item in items:
        link = item.get("VideoLink", item.get("Link", ""))
        ts = item.get("Date", item.get("date", ""))

        insert_event(
            db,
            platform=PLATFORM,
            category="browse",
            timestamp=ts,
            title="Favorited video",
            url=link if link.startswith("http") else None,
            raw_json=json.dumps(item),
        )
        count += 1
    return count


def _parse_profile_info(profile_data: dict, db: sqlite3.Connection) -> None:
    profile_info = profile_data.get("Profile Information", profile_data)
    if isinstance(profile_info, dict):
        info = profile_info.get("ProfileMap", profile_info)
        if isinstance(info, dict):
            for key, value in info.items():
                if isinstance(value, str):
                    insert_profile(
                        db,
                        platform=PLATFORM,
                        category="demographic",
                        key=key,
                        value=value,
                    )


def parse(path: Path, db: sqlite3.Connection) -> int:
    """Parse a TikTok data export and insert events into the database."""
    path = Path(path)
    count = 0

    # TikTok exports are a single user_data.json file or a directory containing it
    if path.is_dir():
        json_file = path / "user_data.json"
        if not json_file.exists():
            # Try to find it
            candidates = list(path.rglob("user_data.json"))
            if candidates:
                json_file = candidates[0]
            else:
                db.commit()
                record_import(db, platform=PLATFORM, source_path=str(path), event_count=0)
                db.commit()
                return 0
        path = json_file

    text = path.read_text(encoding="utf-8-sig")
    data = json.loads(text)

    if not isinstance(data, dict):
        db.commit()
        record_import(db, platform=PLATFORM, source_path=str(path), event_count=0)
        db.commit()
        return 0

    # Activity section
    activity = data.get("Activity", {})
    if isinstance(activity, dict):
        video_history = activity.get("Video Browsing History", {})
        if isinstance(video_history, dict):
            items = video_history.get("VideoList", video_history.get("video_list", []))
            count += _parse_video_history(items, db)
        elif isinstance(video_history, list):
            count += _parse_video_history(video_history, db)

        like_list = activity.get("Like List", {})
        if isinstance(like_list, dict):
            items = like_list.get("ItemFavoriteList", like_list.get("item_list", []))
            count += _parse_like_list(items, db)
        elif isinstance(like_list, list):
            count += _parse_like_list(like_list, db)

        comment_history = activity.get("Comment History", {})
        if isinstance(comment_history, dict):
            items = comment_history.get("CommentsList", comment_history.get("comments", []))
            count += _parse_comments(items, db)
        elif isinstance(comment_history, list):
            count += _parse_comments(comment_history, db)

        favorite_videos = activity.get("Favorite Videos", {})
        if isinstance(favorite_videos, dict):
            items = favorite_videos.get("FavoriteVideoList", favorite_videos.get("video_list", []))
            count += _parse_favorites(items, db)
        elif isinstance(favorite_videos, list):
            count += _parse_favorites(favorite_videos, db)

    # Comment section (top-level)
    comment_section = data.get("Comment", {})
    if isinstance(comment_section, dict):
        comments = comment_section.get("Comments", {})
        if isinstance(comments, dict):
            items = comments.get("CommentsList", comments.get("comments", []))
            count += _parse_comments(items, db)
        elif isinstance(comments, list):
            count += _parse_comments(comments, db)

    # Profile section
    profile = data.get("Profile", {})
    if isinstance(profile, dict):
        _parse_profile_info(profile, db)

    db.commit()
    record_import(db, platform=PLATFORM, source_path=str(path), event_count=count)
    db.commit()
    return count
