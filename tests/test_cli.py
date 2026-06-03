"""Tests for the datamirror CLI."""

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from datamirror.cli import cli
from datamirror.db import SCHEMA_SQL, insert_event

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def populated_db(db_path):
    """Create a database with some test events."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    insert_event(conn, platform="google", category="search", timestamp="2024-03-15T10:00:00", title="Searched for python")
    insert_event(conn, platform="google", category="browse", timestamp="2024-03-15T11:00:00", title="Visited github.com")
    insert_event(conn, platform="meta", category="post", timestamp="2024-03-14T09:00:00", title="Shared a photo")
    insert_event(conn, platform="amazon", category="purchase", timestamp="2024-03-13T14:00:00", title="USB-C Cable", body="Order: 123; Price: $12.99")
    conn.commit()
    conn.close()
    return db_path


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "datamirror" in result.output


def test_import_google(db_path):
    runner = CliRunner()
    fixture = str(FIXTURES / "google_activity.json")
    result = runner.invoke(cli, ["--db", str(db_path), "import", "google", fixture])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "5" in result.output


def test_import_meta(db_path):
    runner = CliRunner()
    fixture = str(FIXTURES / "meta_posts.json")
    result = runner.invoke(cli, ["--db", str(db_path), "import", "meta", fixture])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "3" in result.output


def test_import_amazon(db_path):
    runner = CliRunner()
    fixture = str(FIXTURES / "amazon_orders.csv")
    result = runner.invoke(cli, ["--db", str(db_path), "import", "amazon", fixture])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "5" in result.output


def test_import_apple(db_path):
    runner = CliRunner()
    fixture = str(FIXTURES / "apple_appstore.csv")
    result = runner.invoke(cli, ["--db", str(db_path), "import", "apple", fixture])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "4" in result.output


def test_import_tiktok(db_path):
    runner = CliRunner()
    fixture = str(FIXTURES / "tiktok_userdata.json")
    result = runner.invoke(cli, ["--db", str(db_path), "import", "tiktok", fixture])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "7" in result.output


def test_timeline_empty(db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(db_path), "timeline"])
    assert result.exit_code == 0
    assert "No events found" in result.output


def test_timeline_with_events(populated_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(populated_db), "timeline"])
    assert result.exit_code == 0
    assert "google/search" in result.output
    assert "Searched for python" in result.output


def test_timeline_platform_filter(populated_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(populated_db), "timeline", "--platform", "meta"])
    assert result.exit_code == 0
    assert "meta/post" in result.output
    assert "google" not in result.output


def test_timeline_category_filter(populated_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(populated_db), "timeline", "--category", "purchase"])
    assert result.exit_code == 0
    assert "amazon/purchase" in result.output
    assert "google" not in result.output


def test_timeline_limit(populated_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(populated_db), "timeline", "--limit", "2"])
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().split("\n") if line.startswith("[")]
    assert len(lines) == 2


def test_stats_empty(db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(db_path), "stats"])
    assert result.exit_code == 0
    assert "No data imported" in result.output


def test_stats_with_events(populated_db):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(populated_db), "stats"])
    assert result.exit_code == 0
    assert "Total events: 4" in result.output
    assert "google" in result.output
    assert "meta" in result.output
    assert "amazon" in result.output


def test_delete_request_gdpr(db_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db", str(db_path), "delete-request", "google", "--name", "Test Person"],
    )
    assert result.exit_code == 0
    assert "Google LLC" in result.output
    assert "Article 17" in result.output
    assert "GDPR" in result.output
    assert "Test Person" in result.output


def test_delete_request_ccpa(db_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db", str(db_path), "delete-request", "meta", "--name", "Test Person", "--regulation", "ccpa"],
    )
    assert result.exit_code == 0
    assert "Meta Platforms" in result.output
    assert "CCPA" in result.output
    assert "Section 1798.105" in result.output


def test_delete_request_to_file(db_path, tmp_path):
    output_file = tmp_path / "letter.txt"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--db", str(db_path),
            "delete-request", "google",
            "--name", "Test Person",
            "--output", str(output_file),
        ],
    )
    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "Google LLC" in content


def test_delete_request_all_platforms(db_path):
    """Verify deletion request generation works for every supported platform."""
    runner = CliRunner()
    for platform in ["google", "meta", "amazon", "apple", "tiktok"]:
        result = runner.invoke(
            cli,
            ["--db", str(db_path), "delete-request", platform, "--name", "Test Person"],
        )
        assert result.exit_code == 0
        assert "Deletion" in result.output or "deletion" in result.output


def test_import_invalid_platform(db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(db_path), "import", "badplatform", "."])
    assert result.exit_code != 0


def test_purge_with_confirmation(populated_db):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db", str(populated_db), "purge", "google", "--yes"],
    )
    assert result.exit_code == 0
    assert "Deleted" in result.output

    # Verify google events are gone
    result2 = runner.invoke(cli, ["--db", str(populated_db), "timeline", "--platform", "google"])
    assert "No events found" in result2.output


def test_purge_abort(populated_db):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db", str(populated_db), "purge", "google"],
        input="n\n",
    )
    assert result.exit_code == 0
    assert "Aborted" in result.output
