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
pipeline.py          Orchestrator used by both the CLI and the web app
web_app.py              Flask web server (landing page + /subscribe endpoint)
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

## Quickstart
 
### 1. Clone the repo
 
```bash
git clone https://github.com/YOUR_USERNAME/ai-weekly-digest.git
cd ai-weekly-digest
```
 
### 2. Install dependencies
 
```bash
pip install -r requirements.txt
```
 
### 3. Configure your keys
 
```bash
cp .env.example .env
```
 
Open `.env` and fill in:
 
```env
# LLM (Gemini free tier — get a key at aistudio.google.com)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash-lite
 
# Gmail (use an App Password, not your regular password)
# Generate at: myaccount.google.com → Security → 2-Step Verification → App passwords
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
DIGEST_RECIPIENT=you@gmail.com
```
 
### 4. Run
 
**Option A — Web UI** (recommended for first-time use):
```bash
python app.py
```
Opens `http://localhost:5000` in your browser. Enter any email and click **Send digest**.
 
**Option B — CLI** (good for automation/scheduling):
```bash
python app/main.py
```
Runs the full pipeline, saves `newsletter.html` locally, and sends the email.
 
---
 
## How the cache works
 
The collection + AI analysis steps are expensive (~5–10 min, and they use your Gemini quota). To avoid re-running them unnecessarily, results are cached by date:
 
| File | What it contains | Delete to re-run |
|---|---|---|
| `data_collected.json` | Raw collected + cleaned articles | Collection step |
| `data_output_sample.json` | AI-analyzed articles (scores, summaries) | AI analysis step |
 
Neither file is re-run automatically, if they exist, they're loaded and the pipeline skips straight to newsletter generation. Delete whichever file you want to re-run from that point forward.
 
**Typical weekly flow:** delete both files, run once. Done.

---
## Automating weekly runs
 
If you want this to run automatically every Sunday without touching it, add a scheduled task:
 
**Windows (Task Scheduler):**
```
Action: Start a program
Program: python
Arguments: C:\path\to\ai-weekly-digest\main.py
Trigger: Weekly, Sunday, 09:00
```
 
**Mac/Linux (cron):**
```bash
crontab -e
# Add this line:
0 9 * * 0 cd /path/to/ai-weekly-digest && python main.py
```
 
Make sure to delete `data_collected.json` and `data_output_sample.json` at the start of each week (or add that to the script) so fresh news is collected.
 
---

