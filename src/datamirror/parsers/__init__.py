"""Parser registry for datamirror."""

from __future__ import annotations

from datamirror.parsers import amazon, apple, google, meta, tiktok

PARSERS = {
    "google": google.parse,
    "meta": meta.parse,
    "amazon": amazon.parse,
    "apple": apple.parse,
    "tiktok": tiktok.parse,
}
