"""FastAPI web application for the datamirror dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from datamirror.db import (
    get_connection,
    get_stats,
    query_timeline,
    search_events,
    export_events,
    count_events,
    get_import_history,
)

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="datamirror", version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), auto_reload=True)

    def _db():
        return get_connection(db_path)

    def _render(template_name: str, context: dict) -> HTMLResponse:
        template = env.get_template(template_name)
        html = template.render(**context)
        return HTMLResponse(content=html)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        db = _db()
        data = get_stats(db)
        db.close()
        return _render("index.html", {"stats": data})

    @app.get("/timeline", response_class=HTMLResponse)
    async def timeline_page(
        request: Request,
        platform: str | None = Query(None),
        category: str | None = Query(None),
        after: str | None = Query(None),
        before: str | None = Query(None),
        limit: int = Query(20),
        offset: int = Query(0),
    ):
        db = _db()
        events = query_timeline(
            db,
            platform=platform,
            category=category,
            after=after,
            before=before,
            limit=limit,
            offset=offset,
        )
        stats = get_stats(db)
        db.close()

        # If this is an HTMX request for more rows, return only the partial
        if request.headers.get("HX-Request"):
            row_template = env.get_template("partials/event_row.html")
            rendered_rows = []
            for event in events:
                rendered_rows.append(row_template.render(event=event))
            html = "\n".join(rendered_rows)
            return HTMLResponse(content=html)

        return _render(
            "timeline.html",
            {
                "events": events,
                "stats": stats,
                "platform": platform,
                "category": category,
                "after": after,
                "before": before,
                "limit": limit,
                "offset": offset,
            },
        )

    @app.get("/stats", response_class=HTMLResponse)
    async def stats_page(request: Request):
        db = _db()
        data = get_stats(db)
        db.close()
        return _render("index.html", {"stats": data})

    @app.get("/api/events")
    async def api_events(
        platform: str | None = Query(None),
        category: str | None = Query(None),
        after: str | None = Query(None),
        before: str | None = Query(None),
        limit: int = Query(20),
        offset: int = Query(0),
    ):
        db = _db()
        events = query_timeline(
            db,
            platform=platform,
            category=category,
            after=after,
            before=before,
            limit=limit,
            offset=offset,
        )
        db.close()
        return JSONResponse(content=events)

    @app.get("/api/search")
    async def api_search(
        q: str = Query(..., min_length=1),
        platform: str | None = Query(None),
        category: str | None = Query(None),
        limit: int = Query(20),
    ):
        db = _db()
        events = search_events(
            db, query=q, platform=platform, category=category, limit=limit
        )
        db.close()
        return JSONResponse(content=events)

    @app.get("/api/stats")
    async def api_stats():
        db = _db()
        data = get_stats(db)
        db.close()
        return JSONResponse(content=data)

    @app.get("/api/export")
    async def api_export(
        platform: str | None = Query(None),
        category: str | None = Query(None),
        after: str | None = Query(None),
        before: str | None = Query(None),
    ):
        db = _db()
        events = export_events(
            db, platform=platform, category=category, after=after, before=before
        )
        db.close()
        return JSONResponse(content=events)

    @app.get("/api/history")
    async def api_history():
        db = _db()
        imports = get_import_history(db)
        db.close()
        return JSONResponse(content=imports)

    return app
