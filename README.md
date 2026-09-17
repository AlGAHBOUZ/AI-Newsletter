# AI Weekly Digest

An automated Python application that collects the week's most important AI news, summarizes it using LLMs, filters by relevance, and delivers a concise professional newsletter via email.

---

## Overview

The system monitors five source types, processes everything through a multi-stage pipeline, and produces a structured HTML newsletter organized into editorially meaningful sections. A Flask web app allows anyone to request the current week's digest by entering their email.

---

## Architecture

```
app/collectors/          One module per source. Each returns a list of Article objects.
app/processors/          Stateless transforms: deduplicate → clean → summarize → categorize
app/newsletter/          filter.py · html.py · email.py
app/pipeline.py          Orchestrator used by both the CLI and the web app
main_app.py              Flask web server (landing page + /subscribe endpoint)
templates/               index.html — landing page served by Flask
app/main.py              CLI entry point for local runs
app/config.py            All settings loaded from .env — nothing hardcoded
app/models.py            Article dataclass — the single internal data format
```

---

## Pipeline

Each stage saves its output so subsequent stages can be skipped on re-runs — useful when iterating on prompts or newsletter design without burning API quota.

```
Collect                     hackernews · openai_blog · google_ai_blog
    │                       anthropic_blog · youtube (transcripts via yt-dlp)
    ▼
Deduplicate                 URL normalization + title/source matching
    │
    ▼
Enrich                      Fetch full article text for link-posts (trafilatura)
    │
    ▼
Clean                       Drop empty content, titles-only, very short articles
    │  ← saved to data_collected.json
    ▼
AI Analysis                 One LLM call per article: summary · why it matters
    │                       category · relevance score (1–10)
    │  ← saved to data_YYYY-MM-DD.json (daily cache) / data_output_sample.json (CLI)
    ▼
Filter                      Score < 5 dropped · Score 5–6 kept only if summary
    │                       has sufficient substance (> 60 chars)
    ▼
Generate Newsletter         Sections: Executive Summary · Major Releases · AI Tools
    │                       Tutorials · Research · Industry News · Builder's Corner
    │                       Action Items (score 8+, tool/tutorial categories only)
    ▼
Send Email                  Gmail SMTP with App Password · HTML + plain-text fallback
```

---

## Sources

| Source | Method |
|---|---|
| OpenAI Blog | RSS feed |
| Google AI Blog | RSS feed |
| Anthropic News | HTML scrape (no RSS available) |
| Hacker News | Algolia search API |
| YouTube | yt-dlp (channel listing) + youtube-transcript-api |

---

## Tech Stack

| Layer | Library |
|---|---|
| HTTP / scraping | requests · trafilatura · beautifulsoup4 |
| Feed parsing | feedparser |
| YouTube | yt-dlp · youtube-transcript-api |
| LLM | google-genai (Gemini) — OpenAI / Anthropic stubbed |
| Data validation | pydantic · pydantic-settings |
| Web server | Flask · gunicorn |
| Email | stdlib smtplib (no extra dependency) |
| Config | python-dotenv |

Python 3.12+

---

## Configuration

Copy `.env.example` to `.env` and fill in:

```
# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_REQUESTS_PER_MINUTE=10

# Gmail (use an App Password, not your account password)
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
DIGEST_RECIPIENT=you@gmail.com

# Sources — all have sensible defaults, override as needed
HN_MAX_RESULTS=25
BLOG_MAX_RESULTS=20
YOUTUBE_CHANNELS=@AllAboutAI,@mreflow,@TwoMinutePapers
```

Obtain a Gmail App Password at: **myaccount.google.com → Security → 2-Step Verification → App passwords**

---

## Local Usage

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys

python main.py         # full run — collect, analyze, filter, generate, send
```

**Checkpoint behavior** — delete the relevant file to re-run that stage:

| Delete this file | To re-run |
|---|---|
| `data_collected.json` | Collection + enrichment + cleaning |
| `data_output_sample.json` | AI analysis (LLM calls) |
| *(neither)* | Newsletter generation + email only |

---

## Web App

```bash
flask --app app run    # local dev server at http://localhost:5000
```

A user enters their email on the landing page. The server checks for today's cached analysis file (`data_YYYY-MM-DD.json`). If it exists, newsletter generation and delivery are near-instant. If not, the full pipeline runs first (~5–10 min for the first request each day).

---

## Deployment (Render)

1. Push the project to a GitHub repository
2. Create a new **Web Service** on [render.com](https://render.com) and connect the repo — Render detects `render.yaml` automatically
3. Add the following environment variables in the Render dashboard:

```
GEMINI_API_KEY
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
```

The free tier is sufficient for this workload. No credit card required.
