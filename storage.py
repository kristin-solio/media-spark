"""SQLite storage for mention deduplication and brand-context caching."""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "mentions.db")
BRAND_CACHE_PATH = os.getenv("BRAND_CACHE_PATH", "brand_cache.json")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mentions (
                url           TEXT    PRIMARY KEY,
                title         TEXT,
                snippet       TEXT,
                source        TEXT,
                query_used    TEXT,
                first_seen_at TEXT    NOT NULL,
                draft_json    TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at     TEXT    NOT NULL,
                mentions_found INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


def is_first_run() -> bool:
    """Return True if no successful run has been recorded yet."""
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM run_log LIMIT 1").fetchone()
        return row is None
    finally:
        conn.close()


def record_run(mentions_found: int) -> None:
    """Log a completed run so future runs know this isn't the first."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO run_log (run_at, mentions_found) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), mentions_found),
        )
        conn.commit()
    finally:
        conn.close()


def url_seen(url: str) -> bool:
    """Return True if this URL has already been recorded."""
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM mentions WHERE url = ?", (url,)).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_mention(
    url: str,
    title: str,
    snippet: str,
    source: str,
    query_used: str,
) -> bool:
    """Insert a mention. Returns True if inserted, False if duplicate."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO mentions (url, title, snippet, source, query_used, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (url, title, snippet, source, query_used, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_draft(url: str, draft_json: str) -> None:
    """Attach the Claude-generated draft JSON to an existing mention."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE mentions SET draft_json = ? WHERE url = ?",
            (draft_json, url),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Brand-context cache helpers
# ---------------------------------------------------------------------------

def save_brand_cache(brand_context: str) -> None:
    """Persist brand_context to a local JSON file with a timestamp."""
    payload = {
        "brand_context": brand_context,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(BRAND_CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    logger.info("Brand context cached (%d chars)", len(brand_context))


def load_brand_cache() -> Optional[str]:
    """Load the most recent cached brand_context, or None."""
    if not os.path.exists(BRAND_CACHE_PATH):
        return None
    try:
        with open(BRAND_CACHE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ctx = data.get("brand_context")
        if ctx:
            logger.info(
                "Loaded cached brand context from %s (%d chars)",
                data.get("cached_at", "?"),
                len(ctx),
            )
        return ctx
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read brand cache: %s", exc)
        return None
