"""CLI interface for datamirror."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import click

from datamirror.db import (
    get_connection,
    query_timeline,
    get_stats,
    search_events,
    export_events,
    get_import_history,
    delete_events,
)

PLATFORMS = ["google", "meta", "amazon", "apple", "tiktok"]


@click.group()
@click.option("--db", "db_path", default=None, help="Path to the SQLite database file.")
@click.pass_context
def cli(ctx: click.Context, db_path: str | None) -> None:
    """datamirror: Import and browse your personal data exports."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path) if db_path else None


@cli.command(name="import")
@click.argument("platform", type=click.Choice(PLATFORMS))
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def import_cmd(ctx: click.Context, platform: str, path: str) -> None:
    from datamirror.parsers import PARSERS

    db = get_connection(ctx.obj["db_path"])
    parser = PARSERS[platform]
    source_path = Path(path)

    click.echo(f"Importing {platform} data from {source_path}...")
    count = parser(source_path, db)
    db.close()

    click.echo(f"Imported {count:,} events from {platform}.")


@cli.command()
@click.option("--platform", type=click.Choice(PLATFORMS), default=None, help="Filter by platform.")
@click.option("--category", default=None, help="Filter by category (search, post, message, purchase, watch, etc.).")
@click.option("--limit", default=20, help="Number of events to show.")
@click.option("--after", default=None, help="Show events after this date (YYYY-MM-DD).")
@click.option("--before", default=None, help="Show events before this date (YYYY-MM-DD).")
@click.pass_context
def timeline(
    ctx: click.Context,
    platform: str | None,
    category: str | None,
    limit: int,
    after: str | None,
    before: str | None,
) -> None:
    """Show recent events across all platforms."""
    db = get_connection(ctx.obj["db_path"])
    events = query_timeline(
        db, platform=platform, category=category, limit=limit, after=after, before=before
    )
    db.close()

    if not events:
        click.echo("No events found.")
        return

    for event in events:
        ts = event["timestamp"][:19] if event["timestamp"] else "unknown"
        plat = event["platform"]
        cat = event["category"]
        title = event["title"]
        line = f"[{ts}] {plat}/{cat}: {title}"
        if event.get("body"):
            body_preview = event["body"][:80]
            line += f"\n    {body_preview}"
        click.echo(line)
        click.echo()


@cli.command()
@click.argument("query")
@click.option("--platform", type=click.Choice(PLATFORMS), default=None, help="Filter by platform.")
@click.option("--category", default=None, help="Filter by category.")
@click.option("--limit", default=20, help="Maximum results to return.")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    platform: str | None,
    category: str | None,
    limit: int,
) -> None:
    db = get_connection(ctx.obj["db_path"])
    events = search_events(
        db, query=query, platform=platform, category=category, limit=limit
    )
    db.close()

    if not events:
        click.echo(f"No events matching '{query}'.")
        return

    click.echo(f"Found {len(events)} result(s) for '{query}':\n")
    for event in events:
        ts = event["timestamp"][:19] if event["timestamp"] else "unknown"
        plat = event["platform"]
        cat = event["category"]
        title = event["title"]
        line = f"[{ts}] {plat}/{cat}: {title}"
        if event.get("body"):
            body_preview = event["body"][:80]
            line += f"\n    {body_preview}"
        click.echo(line)
        click.echo()


@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show per platform event counts, date ranges, and category breakdowns."""
    db = get_connection(ctx.obj["db_path"])
    data = get_stats(db)
    db.close()

    if not data["platforms"]:
        click.echo("No data imported yet. Run 'datamirror import' first.")
        return

    click.echo(f"Total events: {data['total_events']:,}")
    click.echo()

    for platform, info in data["platforms"].items():
        click.echo(f"  {platform}:")
        click.echo(f"    Events: {info['count']:,}")
        click.echo(f"    Range:  {info['earliest'][:10]} to {info['latest'][:10]}")
        click.echo(f"    Categories:")
        for cat, cnt in sorted(info["categories"].items()):
            click.echo(f"      {cat}: {cnt:,}")
        click.echo()


@cli.command(name="export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"]),
    default="json",
    help="Output format (json or csv).",
)
@click.option("--platform", type=click.Choice(PLATFORMS), default=None, help="Filter by platform.")
@click.option("--category", default=None, help="Filter by category.")
@click.option("--after", default=None, help="Export events after this date (YYYY-MM-DD).")
@click.option("--before", default=None, help="Export events before this date (YYYY-MM-DD).")
@click.option("--output", "output_path", default=None, help="Write to a file instead of stdout.")
@click.pass_context
def export_cmd(
    ctx: click.Context,
    fmt: str,
    platform: str | None,
    category: str | None,
    after: str | None,
    before: str | None,
    output_path: str | None,
) -> None:
    """Export events as JSON or CSV."""
    db = get_connection(ctx.obj["db_path"])
    events = export_events(
        db, platform=platform, category=category, after=after, before=before
    )
    db.close()

    if not events:
        click.echo("No events to export.")
        return

    if fmt == "json":
        text = json.dumps(events, indent=2, ensure_ascii=False)
    else:
        buf = io.StringIO()
        fieldnames = ["id", "platform", "category", "timestamp", "title", "body", "url", "latitude", "longitude"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)
        text = buf.getvalue()

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        click.echo(f"Exported {len(events):,} events to {output_path}")
    else:
        click.echo(text)


@cli.command()
@click.pass_context
def history(ctx: click.Context) -> None:
    """Show the import history log."""
    db = get_connection(ctx.obj["db_path"])
    imports = get_import_history(db)
    db.close()

    if not imports:
        click.echo("No imports recorded yet.")
        return

    click.echo("Import history:\n")
    for rec in imports:
        ts = rec["imported_at"][:19] if rec["imported_at"] else "unknown"
        click.echo(f"  [{ts}] {rec['platform']} | {rec['event_count']:,} events | {rec['source_path']}")


@cli.command(name="purge")
@click.argument("platform", type=click.Choice(PLATFORMS))
@click.option("--category", default=None, help="Only delete events in this category.")
@click.option("--before", default=None, help="Only delete events before this date (YYYY-MM-DD).")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def purge_cmd(
    ctx: click.Context,
    platform: str,
    category: str | None,
    before: str | None,
    yes: bool,
) -> None:
    if not yes:
        msg = f"This will delete {platform} events"
        if category:
            msg += f" in category '{category}'"
        if before:
            msg += f" before {before}"
        msg += ". Continue?"
        if not click.confirm(msg):
            click.echo("Aborted.")
            return

    db = get_connection(ctx.obj["db_path"])
    removed = delete_events(db, platform=platform, category=category, before=before)
    db.close()

    click.echo(f"Deleted {removed:,} events.")


@cli.command(name="delete-request")
@click.argument("platform", type=click.Choice(PLATFORMS))
@click.option("--name", prompt="Your full name", help="Your full name for the request letter.")
@click.option(
    "--regulation",
    type=click.Choice(["gdpr", "ccpa"]),
    default="gdpr",
    help="Which regulation to cite (gdpr or ccpa).",
)
@click.option("--output", "output_path", default=None, help="Write the letter to a file instead of stdout.")
@click.pass_context
def delete_request(
    ctx: click.Context,
    platform: str,
    name: str,
    regulation: str,
    output_path: str | None,
) -> None:
    """Generate a GDPR/CCPA data deletion request letter."""
    from jinja2 import Environment, FileSystemLoader, PackageLoader

    try:
        env = Environment(loader=PackageLoader("datamirror", "templates"))
    except Exception:
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))

    template = env.get_template("deletion_request.txt.j2")

    platform_names = {
        "google": "Google LLC",
        "meta": "Meta Platforms, Inc.",
        "amazon": "Amazon.com, Inc.",
        "apple": "Apple Inc.",
        "tiktok": "TikTok (ByteDance Ltd.)",
    }

    platform_emails = {
        "google": "support-en@google.com",
        "meta": "datarequests@support.facebook.com",
        "amazon": "privacy@amazon.com",
        "apple": "apple-privacy@apple.com",
        "tiktok": "privacy@tiktok.com",
    }

    from datetime import date

    letter = template.render(
        name=name,
        platform=platform,
        platform_name=platform_names.get(platform, platform),
        platform_email=platform_emails.get(platform, ""),
        regulation=regulation,
        date=date.today().isoformat(),
    )

    if output_path:
        Path(output_path).write_text(letter)
        click.echo(f"Deletion request saved to {output_path}")
    else:
        click.echo(letter)


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Print the datamirror version."""
    from datamirror import __version__

    click.echo(f"datamirror {__version__}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=8000, help="Port to listen on.")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int) -> None:
    import uvicorn

    from datamirror.web.app import create_app

    app = create_app(ctx.obj["db_path"])
    click.echo(f"Starting datamirror dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
