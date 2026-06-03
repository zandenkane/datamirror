"""Tests for the datamirror database layer."""

import sqlite3

import pytest

from datamirror.db import (
    count_events,
    get_connection,
    get_stats,
    insert_event,
    insert_profile,
    query_timeline,
    record_import,
)


def test_insert_and_query_event(db):
    insert_event(
        db,
        platform="google",
        category="search",
        timestamp="2024-03-15T10:30:00",
        title="Searched for python sqlite",
    )
    db.commit()

    events = query_timeline(db, limit=10)
    assert len(events) == 1
    assert events[0]["platform"] == "google"
    assert events[0]["category"] == "search"
    assert events[0]["title"] == "Searched for python sqlite"


def test_query_with_platform_filter(db):
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Event 1")
    insert_event(db, platform="meta", category="post", timestamp="2024-03-15T11:00:00", title="Event 2")
    insert_event(db, platform="google", category="browse", timestamp="2024-03-15T12:00:00", title="Event 3")
    db.commit()

    google_events = query_timeline(db, platform="google", limit=10)
    assert len(google_events) == 2
    assert all(e["platform"] == "google" for e in google_events)


def test_query_with_category_filter(db):
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Search 1")
    insert_event(db, platform="meta", category="post", timestamp="2024-03-15T11:00:00", title="Post 1")
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T12:00:00", title="Search 2")
    db.commit()

    searches = query_timeline(db, category="search", limit=10)
    assert len(searches) == 2
    assert all(e["category"] == "search" for e in searches)


def test_query_with_date_filters(db):
    insert_event(db, platform="google", category="search", timestamp="2024-01-15T10:00:00", title="Old event")
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Recent event")
    insert_event(db, platform="google", category="search", timestamp="2024-06-15T10:00:00", title="Future event")
    db.commit()

    events = query_timeline(db, after="2024-02-01", before="2024-05-01", limit=10)
    assert len(events) == 1
    assert events[0]["title"] == "Recent event"


def test_query_order_newest_first(db):
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="First")
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T12:00:00", title="Third")
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T11:00:00", title="Second")
    db.commit()

    events = query_timeline(db, limit=10)
    assert events[0]["title"] == "Third"
    assert events[1]["title"] == "Second"
    assert events[2]["title"] == "First"


def test_query_limit_and_offset(db):
    for i in range(10):
        insert_event(
            db,
            platform="google",
            category="search",
            timestamp=f"2024-03-{15-i:02d}T10:00:00",
            title=f"Event {i}",
        )
    db.commit()

    page1 = query_timeline(db, limit=3, offset=0)
    assert len(page1) == 3

    page2 = query_timeline(db, limit=3, offset=3)
    assert len(page2) == 3
    assert page1[0]["title"] != page2[0]["title"]


def test_query_combined_filters(db):
    """Verify that platform + category + date filters all work together."""
    insert_event(db, platform="google", category="search", timestamp="2024-01-01T10:00:00", title="A")
    insert_event(db, platform="google", category="search", timestamp="2024-06-01T10:00:00", title="B")
    insert_event(db, platform="google", category="browse", timestamp="2024-03-01T10:00:00", title="C")
    insert_event(db, platform="meta", category="search", timestamp="2024-03-01T10:00:00", title="D")
    db.commit()

    events = query_timeline(db, platform="google", category="search", after="2024-05-01", limit=10)
    assert len(events) == 1
    assert events[0]["title"] == "B"


def test_insert_profile(db):
    insert_profile(db, platform="meta", category="demographic", key="name", value="Test User")
    db.commit()

    row = db.execute("SELECT * FROM profiles WHERE platform = 'meta'").fetchone()
    assert row is not None
    assert row["key"] == "name"
    assert row["value"] == "Test User"


def test_record_import(db):
    record_import(db, platform="google", source_path="/tmp/takeout", event_count=100)
    db.commit()

    row = db.execute("SELECT * FROM imports WHERE platform = 'google'").fetchone()
    assert row is not None
    assert row["event_count"] == 100
    assert row["source_path"] == "/tmp/takeout"


def test_get_stats(db):
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="E1")
    insert_event(db, platform="google", category="browse", timestamp="2024-03-16T10:00:00", title="E2")
    insert_event(db, platform="meta", category="post", timestamp="2024-03-14T10:00:00", title="E3")
    db.commit()

    stats = get_stats(db)
    assert stats["total_events"] == 3
    assert "google" in stats["platforms"]
    assert "meta" in stats["platforms"]
    assert stats["platforms"]["google"]["count"] == 2
    assert stats["platforms"]["meta"]["count"] == 1
    assert stats["platforms"]["google"]["categories"]["search"] == 1
    assert stats["platforms"]["google"]["categories"]["browse"] == 1


def test_get_stats_empty(db):
    """Stats on an empty database should return zero totals."""
    stats = get_stats(db)
    assert stats["total_events"] == 0
    assert stats["platforms"] == {}


def test_count_events(db):
    assert count_events(db) == 0
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="E1")
    insert_event(db, platform="meta", category="post", timestamp="2024-03-15T11:00:00", title="E2")
    db.commit()
    assert count_events(db) == 2


def test_event_with_all_fields(db):
    insert_event(
        db,
        platform="google",
        category="location",
        timestamp="2024-03-15T10:00:00",
        title="Location record",
        body="Near downtown",
        url="https://maps.google.com",
        latitude=37.7749,
        longitude=-122.4194,
        raw_json='{"lat": 37.7749}',
    )
    db.commit()

    events = query_timeline(db, limit=1)
    assert len(events) == 1
    e = events[0]
    assert e["latitude"] == 37.7749
    assert e["longitude"] == -122.4194
    assert e["body"] == "Near downtown"
    assert e["url"] == "https://maps.google.com"
    assert e["raw_json"] == '{"lat": 37.7749}'


def test_get_connection_creates_dir(tmp_path):
    """get_connection should create parent directories if they do not exist."""
    deep_path = tmp_path / "sub" / "dir" / "test.db"
    conn = get_connection(deep_path)
    assert deep_path.exists()
    conn.close()


def test_multiple_profiles_same_platform(db):
    """Multiple profile entries for one platform should coexist."""
    insert_profile(db, platform="tiktok", category="demographic", key="userName", value="testuser")
    insert_profile(db, platform="tiktok", category="demographic", key="likesReceived", value="1234")
    db.commit()

    rows = db.execute("SELECT * FROM profiles WHERE platform = 'tiktok'").fetchall()
    assert len(rows) == 2
