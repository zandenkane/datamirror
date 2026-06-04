# Changelog

## 0.1.0 (2026-05-28)

- Parsers for Google Takeout, Meta (Facebook), Amazon, Apple, and TikTok data exports
- SQLite storage with unified events, profiles, and imports tables
- CLI commands: import, timeline, stats, search, export, history, purge, delete-request, serve, version
- Web dashboard with FastAPI, Jinja2 templates, and HTMX
- JSON API endpoints for events, search, stats, export, and import history
- GDPR/CCPA deletion request letter generation
- JSON and CSV export with platform, category, and date range filters
- Full text search across event titles and bodies
- Test suite with fixtures for all five parsers plus CLI and database layer tests
