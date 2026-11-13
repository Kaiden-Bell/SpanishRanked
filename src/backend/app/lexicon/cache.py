"""SQLite cache in front of the online sources, so each word is fetched once.

A failed fetch is remembered briefly (so a dead network isn't hammered) and never replaces a good
cached answer.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable

from .. import db
from .sources import SourceUnavailable

TTL = {"ok": timedelta(days=180), "missing": timedelta(days=30), "error": timedelta(minutes=30)}


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def peek(conn: sqlite3.Connection, source: str, key: str):
    """(status, body) from the cache only; status is None when never fetched."""
    row = conn.execute("SELECT status, body_json FROM lookup_cache WHERE source = ? AND key = ?", (source, key)).fetchone()
    if row is None:
        return None, None
    return row["status"], json.loads(row["body_json"]) if row["body_json"] else None


def cached(conn: sqlite3.Connection, source: str, key: str, fetch: Callable[[], object], now: datetime | None = None):
    """Returns (status, body): 'ok' with data, 'missing' (the source has nothing), or 'error' (try later).

    Writes in its own short transaction, so callers should not be inside one.
    """
    now = now or datetime.now(timezone.utc)
    row = conn.execute(
        "SELECT status, body_json, fetched_at FROM lookup_cache WHERE source = ? AND key = ?", (source, key)
    ).fetchone()
    if row is not None and now - _parse(row["fetched_at"]) < TTL[row["status"]]:
        return row["status"], json.loads(row["body_json"]) if row["body_json"] else None
    try:
        body = fetch()
    except SourceUnavailable:
        if row is not None and row["status"] == "ok":
            return "ok", json.loads(row["body_json"])  # stale but good beats nothing
        status, body = "error", None
    else:
        status = "ok" if body else "missing"
    with conn:
        conn.execute(
            "INSERT INTO lookup_cache (source, key, status, body_json, fetched_at) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (source, key) DO UPDATE SET status = excluded.status, body_json = excluded.body_json,"
            " fetched_at = excluded.fetched_at",
            (source, key, status, json.dumps(body, ensure_ascii=False) if body else None, db.utc_timestamp(now)),
        )
    return status, body
