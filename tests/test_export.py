"""Tests for export, search, purge, and history CLI commands."""

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from datamirror.cli import cli
from datamirror.db import (
    SCHEMA_SQL,
    insert_event,
    search_events,
    export_events,
    delete_events,
    get_import_history,
    record_import,
)


@pytest.fixture
def populated_db_path(tmp_path):
    """Create a database file with test events for CLI testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    insert_event(conn, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python tutorial")
    insert_event(conn, platform="google", category="browse", timestamp="2024-03-15T11:00:00", title="Visited github.com")
    insert_event(conn, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Shared a photo", body="Great day at the park")
    insert_event(conn, platform="amazon", category="purchase", timestamp="2024-03-13T14:00:00", title="USB-C Cable", body="Order: 123; Price: $12.99")
    conn.commit()
    conn.close()
    return db_path


class TestSearchFunction:
    def test_search_by_title(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python")
        insert_event(db, platform="google", category="browse", timestamp="2024-03-15T11:00:00", title="Visited github")
        db.commit()

        results = search_events(db, query="python")
        assert len(results) == 1
        assert "python" in results[0]["title"].lower()

    def test_search_by_body(self, db):
        insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Status update", body="Had a great day at the park")
        db.commit()

        results = search_events(db, query="park")
        assert len(results) == 1
        assert "park" in results[0]["body"]

    def test_search_with_platform_filter(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Python tutorial")
        insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Python is great")
        db.commit()

        results = search_events(db, query="Python", platform="google")
        assert len(results) == 1
        assert results[0]["platform"] == "google"

    def test_search_no_results(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python")
        db.commit()

        results = search_events(db, query="nonexistent")
        assert len(results) == 0

    def test_search_limit(self, db):
        for i in range(10):
            insert_event(db, platform="google", category="search", timestamp=f"2024-03-{15-i:02d}T10:00:00", title=f"Searched for item {i}")
        db.commit()

        results = search_events(db, query="item", limit=3)
        assert len(results) == 3


class TestExportFunction:
    def test_export_all(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Event 1")
        insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Event 2")
        db.commit()

        events = export_events(db)
        assert len(events) == 2

    def test_export_filtered(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Event 1")
        insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Event 2")
        db.commit()

        events = export_events(db, platform="google")
        assert len(events) == 1
        assert events[0]["platform"] == "google"

    def test_export_date_range(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-01-15T10:00:00", title="Old")
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Recent")
        insert_event(db, platform="google", category="search", timestamp="2024-06-15T10:00:00", title="Future")
        db.commit()

        events = export_events(db, after="2024-02-01", before="2024-04-01")
        assert len(events) == 1
        assert events[0]["title"] == "Recent"


class TestDeleteEvents:
    def test_delete_by_platform(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="E1")
        insert_event(db, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="E2")
        db.commit()

        removed = delete_events(db, platform="google")
        assert removed == 1

        rows = db.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
        assert rows["cnt"] == 1

    def test_delete_by_category(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="E1")
        insert_event(db, platform="google", category="browse", timestamp="2024-03-15T11:00:00", title="E2")
        db.commit()

        removed = delete_events(db, platform="google", category="search")
        assert removed == 1

    def test_delete_requires_filter(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="E1")
        db.commit()

        removed = delete_events(db)
        assert removed == 0

    def test_delete_by_date(self, db):
        insert_event(db, platform="google", category="search", timestamp="2024-01-01T10:00:00", title="Old")
        insert_event(db, platform="google", category="search", timestamp="2024-06-01T10:00:00", title="New")
        db.commit()

        removed = delete_events(db, platform="google", before="2024-03-01")
        assert removed == 1


class TestImportHistory:
    def test_get_import_history(self, db):
        record_import(db, platform="google", source_path="/tmp/takeout", event_count=100)
        record_import(db, platform="meta", source_path="/tmp/facebook", event_count=50)
        db.commit()

        imports = get_import_history(db)
        assert len(imports) == 2
        assert imports[0]["platform"] in ("google", "meta")


class TestExportCLI:
    def test_export_json(self, populated_db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "export"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 4

    def test_export_csv(self, populated_db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "export", "--format", "csv"])
        assert result.exit_code == 0
        assert "platform" in result.output
        assert "google" in result.output

    def test_export_to_file(self, populated_db_path, tmp_path):
        output_file = tmp_path / "export.json"
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "export", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert len(data) == 4

    def test_export_filtered(self, populated_db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "export", "--platform", "google"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert all(e["platform"] == "google" for e in data)

    def test_export_empty(self, db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(db_path), "export"])
        assert result.exit_code == 0
        assert "No events to export" in result.output


class TestSearchCLI:
    def test_search_found(self, populated_db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "search", "python"])
        assert result.exit_code == 0
        assert "python" in result.output.lower()
        assert "result(s)" in result.output

    def test_search_not_found(self, populated_db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(populated_db_path), "search", "zzzznonexistent"])
        assert result.exit_code == 0
        assert "No events matching" in result.output


class TestHistoryCLI:
    def test_history_empty(self, db_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["--db", str(db_path), "history"])
        assert result.exit_code == 0
        assert "No imports recorded" in result.output


class TestVersionCLI:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "datamirror" in result.output
        assert "0.1.0" in result.output
