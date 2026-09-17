import logging

import requests
import trafilatura

from models import Article

logger = logging.getLogger(__name__)

# A plain "python-requests" UA gets blocked by some sites; pretend to be a browser.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIWeeklyDigestBot/1.0)"}


def fetch_article_text(url: str, max_chars: int = 8000) -> str | None:
    """Fetch a URL and extract its main article text. Returns None on any failure."""
    try:
        # We fetch with `requests` ourselves (rather than trafilatura's built-in
        # fetcher) so we control timeout/headers/redirects consistently with
        # every other network call in this project, and only hand trafilatura
        # the raw HTML for the part it's actually good at: extraction.
        response = requests.get(url, headers=_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Content fetch failed for %s: %s", url, exc)
        return None

    try:
        text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
    except Exception as exc:
        # Deliberately broad: extraction runs on arbitrary third-party HTML,
        # and one malformed page must never take down the whole run (Reliability NFR).
        logger.warning("Content extraction failed for %s: %s", url, exc)
        return None

    if not text:
        return None
    return text[:max_chars]


def enrich_with_content(articles: list[Article], max_chars: int = 8000) -> list[Article]:
    """
    Fill in `.content` for any article that doesn't already have it
    (e.g. HN link-posts, whose story_text is empty by definition).
    """
    filled, skipped = 0, 0
    for article in articles:
        if article.content:
            continue  # already has text (e.g. HN self-posts, or a collector that provided it)
        text = fetch_article_text(article.url, max_chars=max_chars)
        if text:
            article.content = text
            filled += 1
        else:
            skipped += 1
            logger.info("No extractable content for: %s (%s)", article.title, article.url)

    logger.info("Content enrichment: %d filled, %d skipped", filled, skipped)
    return articles