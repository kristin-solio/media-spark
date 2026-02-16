"""Send the daily digest email via SendGrid."""

import logging
import os
from datetime import date

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Mail

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ALERT_TO_EMAIL = os.getenv("ALERT_TO_EMAIL", "kristin@soliogrowth.com")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", "")
BRAND_NAME = os.getenv("BRAND_NAME", "Husker Hammer")


def _build_html(mentions: list[dict]) -> str:
    """Build the HTML body for the digest email."""
    today = date.today().isoformat()
    parts: list[str] = []

    parts.append(f"<h2>{BRAND_NAME} – Daily Mention Digest ({today})</h2>")

    if not mentions:
        parts.append(
            "<p>No new mentions found in the last 24 hours. "
            "We searched Reddit (including r/Omaha and r/Nebraska), Nextdoor, "
            "and general web sources. We'll check again tomorrow.</p>"
        )
        return "\n".join(parts)

    parts.append(f"<p><strong>{len(mentions)} new mention(s)</strong> discovered.</p><hr>")

    for idx, m in enumerate(mentions, 1):
        draft = m.get("draft")
        parts.append(f"<h3>#{idx} – {m.get('source', 'Web')}</h3>")
        parts.append(f"<p><strong>Title:</strong> {m.get('title', '(no title)')}</p>")
        parts.append(f"<p><strong>Snippet:</strong> {m.get('snippet', '')}</p>")
        parts.append(
            f'<p><strong>Link:</strong> <a href="{m["url"]}">{m["url"]}</a></p>'
        )

        if draft:
            respond = draft.get("respond_publicly", "?")
            rationale = draft.get("rationale", "")
            parts.append(
                f"<p><strong>Respond publicly?</strong> {respond} — {rationale}</p>"
            )
            parts.append("<ul>")
            parts.append(
                f"<li><strong>A) Short:</strong> {draft.get('option_a_short', '')}</li>"
            )
            parts.append(
                f"<li><strong>B) Friendly:</strong> {draft.get('option_b_friendly', '')}</li>"
            )
            parts.append(
                f"<li><strong>C) Professional:</strong> {draft.get('option_c_professional', '')}</li>"
            )
            parts.append("</ul>")
        else:
            parts.append("<p><em>(Draft could not be generated for this mention.)</em></p>")

        parts.append("<hr>")

    return "\n".join(parts)


def send_digest(mentions: list[dict]) -> bool:
    """Send the daily digest email. Returns True on success."""
    if not SENDGRID_API_KEY:
        logger.error("SENDGRID_API_KEY is not set; cannot send email")
        return False
    if not ALERT_FROM_EMAIL:
        logger.error("ALERT_FROM_EMAIL is not set; cannot send email")
        return False

    today = date.today().isoformat()
    subject = f"[Daily Mentions] {BRAND_NAME} - {today}"
    html_body = _build_html(mentions)

    message = Mail(
        from_email=ALERT_FROM_EMAIL,
        to_emails=ALERT_TO_EMAIL,
        subject=subject,
        html_content=Content("text/html", html_body),
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(
            "Email sent to %s (status %s)", ALERT_TO_EMAIL, response.status_code
        )
        return True
    except Exception:
        logger.exception("Failed to send email via SendGrid")
        return False
