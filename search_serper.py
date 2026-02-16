"""Search for brand mentions using the Serper.dev Google Search API."""

import logging
import os
from typing import Any
from urllib.parse import urlparse

import requests

from storage import insert_mention, url_seen

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
NUM_RESULTS = 10  # top results per query

BRAND_NAME = os.getenv("BRAND_NAME", "Husker Hammer")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "huskerhammer.com")


def _build_queries() -> list[str]:
    """Return the set of search queries to execute."""
    brand_clause = f'("{BRAND_NAME}" OR {BRAND_NAME.replace(" ", "")} OR {BRAND_DOMAIN})'
    return [
        f"{brand_clause} site:reddit.com",
        f"{brand_clause} site:nextdoor.com",
        f"{brand_clause} review OR recommend OR complaint",
    ]


def _search(query: str) -> list[dict[str, Any]]:
    """Execute a single Serper search and return organic results."""
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY is not set; skipping search")
        return []

    payload = {"q": query, "num": NUM_RESULTS}
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(SERPER_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Serper request failed for query '%s': %s", query, exc)
        return []

    return data.get("organic", [])


def _source_from_url(url: str) -> str:
    """Derive a human-readable source label from a URL."""
    host = urlparse(url).netloc.lower()
    if "reddit.com" in host:
        return "Reddit"
    if "nextdoor.com" in host:
        return "Nextdoor"
    if "facebook.com" in host:
        return "Facebook"
    if "yelp.com" in host:
        return "Yelp"
    if "google.com" in host:
        return "Google"
    return host


def discover_mentions() -> list[dict[str, str]]:
    """Run all queries and return a list of *new* mentions (not previously seen).

    Each item is a dict with keys: url, title, snippet, source, query_used.
    Side effect: new mentions are inserted into the SQLite database.
    """
    new_mentions: list[dict[str, str]] = []
    seen_urls_this_run: set[str] = set()

    for query in _build_queries():
        logger.info("Searching: %s", query)
        results = _search(query)
        logger.info("  → %d organic results", len(results))

        for item in results:
            url = item.get("link", "")
            if not url or url in seen_urls_this_run:
                continue
            seen_urls_this_run.add(url)

            if url_seen(url):
                continue

            title = item.get("title", "(no title)")
            snippet = item.get("snippet", "")
            source = _source_from_url(url)

            inserted = insert_mention(
                url=url,
                title=title,
                snippet=snippet,
                source=source,
                query_used=query,
            )
            if inserted:
                new_mentions.append(
                    {
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "source": source,
                        "query_used": query,
                    }
                )

    logger.info("Total new mentions discovered: %d", len(new_mentions))
    return new_mentions
