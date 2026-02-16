#!/usr/bin/env python3
"""Husker Hammer Mention Agent – daily brand-mention discovery and digest.

Usage:
    python main.py          # run once (manual or via cron)

Cron example (every day at 8:00 AM local time):
    0 8 * * * cd /path/to/husker-hammer-mention-agent && /path/to/venv/bin/python main.py >> cron.log 2>&1
"""

import logging
import sys

from dotenv import load_dotenv

# Load .env before any module reads os.getenv
load_dotenv()

from brand_scrape import get_brand_context       # noqa: E402
from draft_reply_claude import draft_replies      # noqa: E402
from email_sendgrid import send_digest            # noqa: E402
from search_serper import discover_mentions       # noqa: E402
from storage import init_db, is_first_run, record_run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run() -> None:
    logger.info("=== Husker Hammer Mention Agent – starting run ===")

    # 1. Initialise the database
    init_db()

    # 2. Fetch / cache brand website context
    logger.info("Step 1/4: Building brand context from website…")
    brand_context = get_brand_context()
    logger.info("Brand context ready (%d chars)", len(brand_context))

    # 3. Discover new mentions via Serper
    #    First run → search last 90 days (backfill).
    #    Subsequent runs → search last 24 hours only.
    first = is_first_run()
    if first:
        logger.info("Step 2/4: First run detected – searching last 90 days…")
    else:
        logger.info("Step 2/4: Searching for new mentions (last 24 hours)…")
    new_mentions = discover_mentions(first_run=first)

    # 4. Draft replies for new mentions only (keeps Claude costs minimal)
    enriched: list[dict] = []
    if new_mentions:
        logger.info("Step 3/4: Drafting replies for %d new mention(s)…", len(new_mentions))
        enriched = draft_replies(new_mentions, brand_context)
    else:
        logger.info("Step 3/4: No new mentions – skipping Claude drafts")

    # 5. Send the daily digest email
    logger.info("Step 4/4: Sending daily digest email…")
    ok = send_digest(enriched)

    # 6. Record this run so the next one uses the 24-hour window
    record_run(mentions_found=len(new_mentions))

    if ok:
        logger.info("=== Run complete – email sent successfully ===")
    else:
        logger.error("=== Run complete – email delivery failed ===")
        sys.exit(1)


if __name__ == "__main__":
    run()
