"""Shared fixtures for datamirror tests."""

import sqlite3
from pathlib import Path

import pytest

from datamirror.db import SCHEMA_SQL, insert_event, insert_profile


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    """Create an in memory SQLite database with the schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def populated_db(db):
    """Database pre loaded with events from multiple platforms."""
    insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python")
    insert_event(db, platform="google", category="browse", timestamp="2024-03-15T11:00:00", title="Visited github.com")
    insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Shared a photo")
    insert_event(db, platform="amazon", category="purchase", timestamp="2024-03-13T14:00:00", title="USB-C Cable", body="Order: 123; Price: $12.99")
    insert_event(db, platform="apple", category="purchase", timestamp="2024-03-12T08:00:00", title="Pixelmator Pro", body="Developer: Pixelmator Team; Price: $39.99")
    insert_event(db, platform="tiktok", category="watch", timestamp="2024-03-11T20:00:00", title="Watched video", url="https://www.tiktok.com/@user/video/123")
    db.commit()
    return db


@pytest.fixture
def db_path(tmp_path):
    """Temporary database file path for CLI tests."""
    return tmp_path / "test.db"
