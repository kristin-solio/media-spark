"""Fetch a web page and return its readable text content."""

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HuskerHammerMentionBot/1.0; "
            "+https://github.com/soliogrowth/husker-hammer-mention-agent)"
        ),
    }
)

REQUEST_TIMEOUT = 15  # seconds


def fetch_text(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
    """Download *url* and return cleaned visible text, or None on failure."""
    try:
        resp = _SESSION.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove non-visible elements
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Collapse blank lines
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_internal_links(url: str, base_domain: str) -> list[str]:
    """Return a list of absolute internal links found on *url*."""
    try:
        resp = _SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s for link extraction: %s", url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        # Resolve relative links
        if href.startswith("/"):
            href = url.rstrip("/") + href
        # Keep only links on the same domain
        if base_domain in href and href not in links:
            links.append(href)
    return links
