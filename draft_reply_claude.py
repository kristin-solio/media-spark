"""Draft reply options for each mention using the Anthropic Claude Messages API."""

import json
import logging
import os

import requests

from storage import update_draft

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
MAX_TOKENS = 1024

BRAND_NAME = os.getenv("BRAND_NAME", "Husker Hammer")

SYSTEM_PROMPT = f"""\
You are a social-media response strategist for {BRAND_NAME}.

You will receive:
1. **brand_context** – factual content scraped from the brand's own website.
2. **mention** – a title, snippet, source, and URL of a public mention.

Your job:
- Decide: "Should we respond publicly? YES or NO" plus a 1-sentence rationale.
- Then provide three draft response options:
  A) Short (1-2 sentences)
  B) Friendly / conversational
  C) Ultra-professional / formal

Rules you MUST follow:
- NEVER invent pricing, warranties, service areas, or policies that are not present in the brand_context.
- If the mention is a complaint: apologize, offer to resolve, and suggest moving to a private channel (phone/email/DM).
- If the mention is praise: thank them and offer further help.
- If the mention is a recommendation request: be concise, helpful, and invite them to schedule an inspection or estimate.
- Do NOT reveal or hint that an AI wrote the response.
- Write in the voice of a real team member at {BRAND_NAME}.

Return valid JSON (no markdown fences) with this exact schema:
{{
  "respond_publicly": "YES" or "NO",
  "rationale": "...",
  "option_a_short": "...",
  "option_b_friendly": "...",
  "option_c_professional": "..."
}}
"""


def _call_claude(user_content: str) -> dict | None:
    """Send a request to the Anthropic Messages API and parse the JSON response."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set; skipping draft")
        return None

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    try:
        resp = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Anthropic API request failed: %s", exc)
        return None

    # Extract assistant text
    try:
        text = data["content"][0]["text"]
    except (KeyError, IndexError):
        logger.error("Unexpected Anthropic response shape: %s", data)
        return None

    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Claude response was not valid JSON:\n%s", text)
        return None


def draft_replies(
    mentions: list[dict[str, str]],
    brand_context: str,
) -> list[dict]:
    """For each mention, call Claude and return enriched mention dicts.

    Each returned dict has the original mention fields plus a 'draft' key
    containing the parsed JSON from Claude (or None on failure).
    """
    results: list[dict] = []

    for mention in mentions:
        user_message = (
            f"## Brand Context\n{brand_context}\n\n"
            f"## Mention\n"
            f"Source: {mention['source']}\n"
            f"Title: {mention['title']}\n"
            f"Snippet: {mention['snippet']}\n"
            f"URL: {mention['url']}\n"
        )

        logger.info("Drafting reply for: %s", mention["url"])
        draft = _call_claude(user_message)

        if draft:
            update_draft(mention["url"], json.dumps(draft))

        enriched = {**mention, "draft": draft}
        results.append(enriched)

    return results
