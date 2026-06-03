"""Tests for the datamirror web API endpoints."""

import sqlite3
from pathlib import Path

import pytest

from datamirror.db import SCHEMA_SQL, insert_event
from datamirror.web.app import create_app

try:
    from starlette.testclient import TestClient
    HAS_TESTCLIENT = True
except ImportError:
    HAS_TESTCLIENT = False


@pytest.fixture
def populated_db_path(tmp_path):
    """Create a database file with test events."""
    db_path = tmp_path / "web_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    insert_event(conn, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python")
    insert_event(conn, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Shared a photo")
    insert_event(conn, platform="amazon", category="purchase", timestamp="2024-03-13T14:00:00", title="USB-C Cable", body="Order: 123; Price: $12.99")
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def empty_db_path(tmp_path):
    """Create an empty database file."""
    db_path = tmp_path / "empty_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.close()
    return db_path


@pytest.mark.skipif(not HAS_TESTCLIENT, reason="starlette not installed")
class TestAPIEndpoints:
    def test_api_events_returns_json(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_api_events_platform_filter(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/events?platform=google")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "google"

    def test_api_events_category_filter(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/events?category=purchase")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "amazon"

    def test_api_events_limit(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/events?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_api_events_offset(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/events?limit=2&offset=0")
        data = response.json()
        assert len(data) == 2

    def test_api_search(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/search?q=python")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "python" in data[0]["title"].lower()

    def test_api_search_no_results(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/search?q=zzzznothing")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_api_stats(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 3
        assert "google" in data["platforms"]
        assert "meta" in data["platforms"]
        assert "amazon" in data["platforms"]

    def test_api_export(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/export")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_api_export_filtered(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/export?platform=meta")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["platform"] == "meta"

    def test_api_history(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_api_events_empty_db(self, empty_db_path):
        app = create_app(empty_db_path)
        client = TestClient(app)
        response = client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_api_stats_empty_db(self, empty_db_path):
        app = create_app(empty_db_path)
        client = TestClient(app)
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert data["platforms"] == {}

    def test_index_returns_html(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "datamirror" in response.text

    def test_timeline_returns_html(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/timeline")
        assert response.status_code == 200
        assert "Timeline" in response.text

    def test_stats_page_returns_html(self, populated_db_path):
        app = create_app(populated_db_path)
        client = TestClient(app)
        response = client.get("/stats")
        assert response.status_code == 200
        assert "datamirror" in response.text
