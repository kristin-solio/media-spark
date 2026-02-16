# Husker Hammer Mention Agent

A local Python agent that runs daily via cron, discovers new public mentions of **Husker Hammer** across the web, drafts AI-powered reply options grounded in actual brand website content, and sends a single digest email.

## How it works

1. **Brand grounding** – Crawls `huskerhammer.com` (homepage + up to 10 internal pages) and builds a concise brand-context string. Cached daily so a failed fetch falls back to the last good snapshot.
2. **Mention discovery** – Queries the Serper.dev Google Search API for brand mentions on Reddit, Nextdoor, and general web sources.
3. **Deduplication** – Stores every URL in a local SQLite database (`mentions.db`) with a `UNIQUE` constraint. Only URLs not previously seen are included in the digest.
4. **Draft replies** – For each *new* mention, calls the Anthropic Claude Messages API to produce a public-response recommendation (YES/NO) and three tone options (short, friendly, ultra-professional). Replies are grounded in the brand context and follow strict rules (no invented pricing, appropriate handling of complaints/praise/recommendation requests).
5. **Email digest** – Sends one HTML email via SendGrid with a summary count, each mention's details, and the draft reply options. If there are zero new mentions it still sends a "No new mentions found today" confirmation.

## Prerequisites

- Python 3.10+
- API keys for:
  - [Serper.dev](https://serper.dev/) – Google Search API
  - [Anthropic](https://console.anthropic.com/) – Claude Messages API
  - [SendGrid](https://sendgrid.com/) – Email delivery

## Setup

```bash
# Clone the repo
git clone <repo-url> husker-hammer-mention-agent
cd husker-hammer-mention-agent

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in your API keys
```

### Getting API keys

| Service | Where to get it | Notes |
|---------|----------------|-------|
| **Serper.dev** | https://serper.dev/dashboard | Free tier includes 2,500 searches. |
| **Anthropic** | https://console.anthropic.com/settings/keys | You need credits on your account. |
| **SendGrid** | https://app.sendgrid.com/settings/api_keys | Also verify your sender address under *Sender Authentication*. |

### SendGrid sender verification

The `ALERT_FROM_EMAIL` address **must** be verified in SendGrid before emails will deliver. Go to *Settings → Sender Authentication* and either verify a single sender or authenticate your domain.

## Running manually

```bash
source venv/bin/activate
python main.py
```

## Cron setup

Run daily at 8:00 AM local time:

```
0 8 * * * cd /path/to/husker-hammer-mention-agent && /path/to/husker-hammer-mention-agent/venv/bin/python main.py >> cron.log 2>&1
```

To edit your crontab:

```bash
crontab -e
```

Make sure the paths are absolute. The `>> cron.log 2>&1` redirects both stdout and stderr so you can review logs.

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `SERPER_API_KEY` | *(required)* | Serper.dev API key |
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-latest` | Claude model to use for drafting |
| `SENDGRID_API_KEY` | *(required)* | SendGrid API key |
| `ALERT_TO_EMAIL` | `kristin@soliogrowth.com` | Recipient of the daily digest |
| `ALERT_FROM_EMAIL` | *(required)* | Verified SendGrid sender address |
| `BRAND_NAME` | `Husker Hammer` | Brand name used in search queries |
| `BRAND_DOMAIN` | `huskerhammer.com` | Brand domain for link filtering |
| `BRAND_URL` | `http://huskerhammer.com/` | Homepage URL for brand scraping |

## Project structure

```
├── main.py                 # Entrypoint – orchestrates the full pipeline
├── search_serper.py        # Serper.dev Google Search API integration
├── storage.py              # SQLite dedup + brand-cache helpers
├── fetch_page.py           # Generic page fetching & text extraction
├── brand_scrape.py         # Brand website crawling & context building
├── draft_reply_claude.py   # Anthropic Claude API for draft replies
├── email_sendgrid.py       # SendGrid daily digest email
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── README.md               # This file
```

## Troubleshooting

### Empty search results
- Verify your `SERPER_API_KEY` is valid and has remaining quota at https://serper.dev/dashboard.
- The brand may genuinely have no new indexed mentions. The agent will send a "No new mentions" email in this case.

### Rate limits
- **Serper**: Free tier allows 2,500 queries/month. The agent uses 3 queries per run (≈90/month on daily cron).
- **Anthropic**: Each new mention triggers one Claude API call. Costs depend on model and response length; `claude-3-5-sonnet-latest` is cost-effective. If you hit rate limits, reduce the number of mentions processed or switch to a smaller model.
- **SendGrid**: Free tier allows 100 emails/day. One digest email per day is well within limits.

### Email not arriving
- Check that `ALERT_FROM_EMAIL` is a verified sender in SendGrid.
- Look at the SendGrid *Activity Feed* for delivery status.
- Check spam/junk folders.
- Ensure `SENDGRID_API_KEY` has "Mail Send" permission.

### Brand website fetch fails
- The agent caches the last successful scrape in `brand_cache.json`. If `huskerhammer.com` is temporarily down, the cached version is used automatically.
- If you see "(Brand website content unavailable.)" in drafts, the site has never been reachable. Verify the `BRAND_URL` setting.

### Database issues
- The SQLite database `mentions.db` is created automatically on first run.
- To reset and re-discover all mentions, delete `mentions.db` and run again.
