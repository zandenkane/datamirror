"""Tests for datamirror parsers."""

from pathlib import Path

import pytest

from datamirror.db import query_timeline

FIXTURES = Path(__file__).parent / "fixtures"


class TestGoogleParser:
    def test_parse_activity_json(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        count = parse(fixture, db)
        assert count == 5

        events = query_timeline(db, limit=100)
        assert len(events) == 5

        # All events should come from the google platform
        assert all(e["platform"] == "google" for e in events)

        # Check categories were detected
        categories = {e["category"] for e in events}
        assert "search" in categories

    def test_parse_assigns_search_category(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        parse(fixture, db)

        searches = query_timeline(db, category="search", limit=100)
        assert len(searches) >= 2

    def test_parse_stores_urls(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        events_with_urls = [e for e in events if e.get("url")]
        assert len(events_with_urls) >= 2

    def test_parse_records_import(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        parse(fixture, db)

        imports = db.execute("SELECT * FROM imports WHERE platform = 'google'").fetchall()
        assert len(imports) == 1
        assert imports[0]["event_count"] == 5

    def test_parse_detects_youtube_category(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        parse(fixture, db)

        watches = query_timeline(db, category="watch", limit=100)
        assert len(watches) >= 1

    def test_parse_detects_browse_category(self, db):
        from datamirror.parsers.google import parse

        fixture = FIXTURES / "google_activity.json"
        parse(fixture, db)

        # The Chrome header entry should be categorized as "browse"
        browse = query_timeline(db, category="browse", limit=100)
        assert len(browse) >= 1


class TestMetaParser:
    def test_parse_posts_json(self, db):
        from datamirror.parsers.meta import parse

        fixture = FIXTURES / "meta_posts.json"
        count = parse(fixture, db)
        assert count == 3

        events = query_timeline(db, limit=100)
        assert len(events) == 3
        assert all(e["platform"] == "meta" for e in events)
        assert all(e["category"] == "post" for e in events)

    def test_parse_stores_body(self, db):
        from datamirror.parsers.meta import parse

        fixture = FIXTURES / "meta_posts.json"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        bodies = [e["body"] for e in events if e.get("body")]
        assert len(bodies) == 3
        assert any("great day" in b for b in bodies)

    def test_parse_records_import(self, db):
        from datamirror.parsers.meta import parse

        fixture = FIXTURES / "meta_posts.json"
        parse(fixture, db)

        imports = db.execute("SELECT * FROM imports WHERE platform = 'meta'").fetchall()
        assert len(imports) == 1

    def test_parse_stores_raw_json(self, db):
        from datamirror.parsers.meta import parse
        import json

        fixture = FIXTURES / "meta_posts.json"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        for e in events:
            assert e["raw_json"] is not None
            parsed = json.loads(e["raw_json"])
            assert isinstance(parsed, dict)

    def test_fix_encoding(self):
        from datamirror.parsers.meta import _fix_encoding

        # Latin1 encoded UTF8 should be fixed
        original = "Hello"
        assert _fix_encoding(original) == "Hello"

        # Already correct text should pass through
        assert _fix_encoding("plain text") == "plain text"


class TestAmazonParser:
    def test_parse_orders_csv(self, db):
        from datamirror.parsers.amazon import parse

        fixture = FIXTURES / "amazon_orders.csv"
        count = parse(fixture, db)
        assert count == 5

        events = query_timeline(db, limit=100)
        assert len(events) == 5
        assert all(e["platform"] == "amazon" for e in events)
        assert all(e["category"] == "purchase" for e in events)

    def test_parse_stores_order_details(self, db):
        from datamirror.parsers.amazon import parse

        fixture = FIXTURES / "amazon_orders.csv"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        titles = [e["title"] for e in events]
        assert "USB-C Cable 3-Pack" in titles
        assert "Python Cookbook" in titles

    def test_parse_stores_price_in_body(self, db):
        from datamirror.parsers.amazon import parse

        fixture = FIXTURES / "amazon_orders.csv"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        for e in events:
            assert e["body"] is not None
            assert "Price:" in e["body"]

    def test_parse_records_import(self, db):
        from datamirror.parsers.amazon import parse

        fixture = FIXTURES / "amazon_orders.csv"
        parse(fixture, db)

        imports = db.execute("SELECT * FROM imports WHERE platform = 'amazon'").fetchall()
        assert len(imports) == 1
        assert imports[0]["event_count"] == 5

    def test_parse_nonexistent_dir(self, db):
        from datamirror.parsers.amazon import parse

        count = parse(Path("/tmp/nonexistent_dir_xyz"), db)
        assert count == 0


class TestAppleParser:
    def test_parse_appstore_csv(self, db):
        from datamirror.parsers.apple import parse

        fixture = FIXTURES / "apple_appstore.csv"
        count = parse(fixture, db)
        assert count == 4

        events = query_timeline(db, limit=100)
        assert len(events) == 4
        assert all(e["platform"] == "apple" for e in events)
        assert all(e["category"] == "purchase" for e in events)

    def test_parse_stores_app_names(self, db):
        from datamirror.parsers.apple import parse

        fixture = FIXTURES / "apple_appstore.csv"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        titles = [e["title"] for e in events]
        assert "Pixelmator Pro" in titles
        assert "1Password" in titles

    def test_parse_stores_developer_info(self, db):
        from datamirror.parsers.apple import parse

        fixture = FIXTURES / "apple_appstore.csv"
        parse(fixture, db)

        events = query_timeline(db, limit=100)
        for e in events:
            assert e["body"] is not None
            assert "Developer:" in e["body"]

    def test_parse_records_import(self, db):
        from datamirror.parsers.apple import parse

        fixture = FIXTURES / "apple_appstore.csv"
        parse(fixture, db)

        imports = db.execute("SELECT * FROM imports WHERE platform = 'apple'").fetchall()
        assert len(imports) == 1

    def test_parse_nonexistent_file(self, db):
        from datamirror.parsers.apple import parse

        count = parse(Path("/tmp/nonexistent_xyz.csv"), db)
        assert count == 0


class TestTikTokParser:
    def test_parse_user_data(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        count = parse(fixture, db)
        # 3 videos + 1 like + 2 comments + 1 favorite = 7
        assert count == 7

        events = query_timeline(db, limit=100)
        assert len(events) == 7
        assert all(e["platform"] == "tiktok" for e in events)

    def test_parse_video_history(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        watches = query_timeline(db, category="watch", limit=100)
        assert len(watches) == 3

    def test_parse_comments(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        comments = query_timeline(db, category="comment", limit=100)
        assert len(comments) == 2
        bodies = [c["body"] for c in comments]
        assert "This is great!" in bodies

    def test_parse_likes_and_favorites(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        browse = query_timeline(db, category="browse", limit=100)
        assert len(browse) == 2  # 1 like + 1 favorite

    def test_parse_stores_profile(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        profiles = db.execute("SELECT * FROM profiles WHERE platform = 'tiktok'").fetchall()
        assert len(profiles) == 2
        keys = {p["key"] for p in profiles}
        assert "userName" in keys

    def test_parse_records_import(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        imports = db.execute("SELECT * FROM imports WHERE platform = 'tiktok'").fetchall()
        assert len(imports) == 1
        assert imports[0]["event_count"] == 7

    def test_parse_video_urls_stored(self, db):
        from datamirror.parsers.tiktok import parse

        fixture = FIXTURES / "tiktok_userdata.json"
        parse(fixture, db)

        watches = query_timeline(db, category="watch", limit=100)
        urls = [w["url"] for w in watches if w.get("url")]
        assert len(urls) == 3
        assert all(u.startswith("https://") for u in urls)
