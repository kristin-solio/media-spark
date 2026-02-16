"""Crawl the brand website and build a concise brand_context string."""

import logging
import os
from typing import Optional

from fetch_page import extract_internal_links, fetch_text
from storage import load_brand_cache, save_brand_cache

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 8000
MAX_PAGES = 10

BRAND_URL = os.getenv("BRAND_URL", "http://huskerhammer.com/")
BRAND_DOMAIN = os.getenv("BRAND_DOMAIN", "huskerhammer.com")


def build_brand_context() -> str:
    """Fetch key brand pages and return a consolidated context string.

    Falls back to the most recent cache if the live fetch fails entirely.
    """
    pages_text: list[str] = []

    # 1. Fetch the homepage
    homepage_text = fetch_text(BRAND_URL)
    if homepage_text:
        pages_text.append(f"[Homepage]\n{homepage_text}")

    # 2. Discover internal links from the homepage (services, about, etc.)
    internal_links = extract_internal_links(BRAND_URL, BRAND_DOMAIN)
    logger.info("Found %d internal links on homepage", len(internal_links))

    visited = {BRAND_URL.rstrip("/")}
    for link in internal_links:
        if len(visited) >= MAX_PAGES:
            break
        normalized = link.rstrip("/")
        if normalized in visited:
            continue
        visited.add(normalized)
        text = fetch_text(link)
        if text:
            pages_text.append(f"[{link}]\n{text}")

    if not pages_text:
        logger.warning("Could not fetch any brand pages; falling back to cache")
        cached = load_brand_cache()
        if cached:
            return cached
        return "(Brand website content unavailable.)"

    combined = "\n\n---\n\n".join(pages_text)

    # Cap to MAX_CONTEXT_CHARS
    if len(combined) > MAX_CONTEXT_CHARS:
        combined = combined[:MAX_CONTEXT_CHARS] + "\n[...truncated]"

    save_brand_cache(combined)
    return combined


def get_brand_context() -> str:
    """Public entry point: try live scrape, fall back to cache."""
    try:
        return build_brand_context()
    except Exception:
        logger.exception("Unexpected error during brand scrape")
        cached = load_brand_cache()
        if cached:
            return cached
        return "(Brand website content unavailable.)"
