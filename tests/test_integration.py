"""Integration test proving datamirror unifies data across platforms."""

from pathlib import Path

from datamirror.db import get_connection, query_timeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_unified_timeline_across_platforms():
    """Import Google and Meta fixtures into one in-memory DB and verify
    the unified timeline contains interleaved events from both platforms,
    proving datamirror actually merges data rather than concatenating it.

    Fixture timestamps (sorted DESC):

        Google  2024-03-15T11:15:00.000Z  Visited stackoverflow.com
        Google  2024-03-15T11:00:00.000Z  Searched for fastapi htmx example
        Meta    2024-03-15T10:53:20       Shared a post       (unix 1710500000)
        Google  2024-03-15T10:30:00.000Z  Searched for python sqlite tutorial
        Meta    2024-03-15T08:06:40       Updated status      (unix 1710400000)
        Google  2024-03-14T20:00:00.000Z  Watched Python Tutorial for Beginners
        Meta    2024-03-14T19:40:00       Shared a link       (unix 1710300000)
        Google  2024-03-14T08:30:00.000Z  Searched for coffee shop near me

    The key assertion: a Meta event sits between two Google events,
    proving true chronological interleaving rather than per-platform
    concatenation.
    """
    # -- Create an in-memory database using get_connection (exercises the fix) --
    conn = get_connection(":memory:")

    # -- Import Google activity --
    from datamirror.parsers.google import parse as google_parse

    google_fixture = FIXTURES / "google_activity.json"
    google_count = google_parse(google_fixture, conn)
    assert google_count == 5, f"Expected 5 Google events, got {google_count}"

    # Verify Google events have correct fields
    google_events = query_timeline(conn, platform="google", limit=100)
    assert len(google_events) == 5
    google_titles = [e["title"] for e in google_events]
    assert "Searched for python sqlite tutorial" in google_titles
    for e in google_events:
        assert e["platform"] == "google"
        assert e["timestamp"]  # non-empty timestamp
        assert e["title"]  # non-empty title

    # -- Import Meta posts --
    from datamirror.parsers.meta import parse as meta_parse

    meta_fixture = FIXTURES / "meta_posts.json"
    meta_count = meta_parse(meta_fixture, conn)
    assert meta_count == 3, f"Expected 3 Meta events, got {meta_count}"

    # Verify Meta events have correct fields
    meta_events = query_timeline(conn, platform="meta", limit=100)
    assert len(meta_events) == 3
    meta_titles = [e["title"] for e in meta_events]
    assert "Shared a post" in meta_titles
    for e in meta_events:
        assert e["platform"] == "meta"
        assert e["timestamp"]  # non-empty timestamp
        assert e["title"]  # non-empty title

    # -- Query the unified timeline (all platforms, sorted by timestamp DESC) --
    timeline = query_timeline(conn, limit=100)
    assert len(timeline) == 8, f"Expected 8 total events, got {len(timeline)}"

    # Both platforms must be present
    platforms_in_timeline = {e["platform"] for e in timeline}
    assert platforms_in_timeline == {"google", "meta"}

    # -- Prove chronological interleaving, not concatenation --
    # In the DESC-sorted timeline, the "Shared a post" Meta event
    # (timestamp 2024-03-15T10:53:20) falls between two Google events:
    #   Google  2024-03-15T11:00:00.000Z  (Searched for fastapi htmx example)
    #   Meta    2024-03-15T10:53:20       (Shared a post)
    #   Google  2024-03-15T10:30:00.000Z  (Searched for python sqlite tutorial)
    timeline_platforms = [e["platform"] for e in timeline]
    timeline_titles = [e["title"] for e in timeline]

    # Find the "Shared a post" Meta event
    meta_post_idx = timeline_titles.index("Shared a post")
    assert timeline_platforms[meta_post_idx] == "meta"

    # The event before it (higher index = earlier in DESC order is wrong;
    # lower index = more recent) should be Google
    assert meta_post_idx > 0, "Meta event should not be the most recent"
    assert meta_post_idx < len(timeline) - 1, "Meta event should not be the oldest"
    assert timeline_platforms[meta_post_idx - 1] == "google", (
        "Event immediately before Meta 'Shared a post' should be Google, "
        f"but got {timeline_platforms[meta_post_idx - 1]}"
    )
    assert timeline_platforms[meta_post_idx + 1] == "google", (
        "Event immediately after Meta 'Shared a post' should be Google, "
        f"but got {timeline_platforms[meta_post_idx + 1]}"
    )

    # Verify the timeline is sorted chronologically (DESC)
    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps, reverse=True), (
        "Timeline should be sorted by timestamp descending"
    )

    conn.close()
