import logging
import re
from datetime import datetime, timezone

import requests
import trafilatura
from bs4 import BeautifulSoup

from models import Article

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.anthropic.com/news"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIWeeklyDigestBot/1.0)"}
_ARTICLE_PATH_RE = re.compile(r"^(https://www\.anthropic\.com)?/news/[a-z0-9\-]+$")


def _fetch_listing_html() -> str | None:
    try:
        response = requests.get(LISTING_URL, headers=_HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("Failed to fetch Anthropic news listing: %s", exc)
        return None


def _parse_listing_html(html: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _ARTICLE_PATH_RE.match(href):
            full_url = href if href.startswith("http") else f"https://www.anthropic.com{href}"
            if full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)
        if len(urls) >= limit:
            break

    return urls


def _discover_article_urls(limit: int) -> list[str]:
    html = _fetch_listing_html()
    if not html:
        return []
    return _parse_listing_html(html, limit)


def _extract_article(url: str) -> Article | None:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch Anthropic article %s: %s", url, exc)
        return None

    doc = trafilatura.bare_extraction(response.text, with_metadata=True)
    if not doc or not doc.title:
        logger.info("No extractable content for Anthropic article: %s", url)
        return None

    published_at = datetime.now(tz=timezone.utc)
    if doc.date:
        try:
            published_at = datetime.fromisoformat(doc.date).replace(tzinfo=timezone.utc)
        except ValueError:
            pass  # keep the "now" fallback rather than failing the whole article

    return Article(
        title=doc.title,
        url=url,
        source="anthropic_blog",
        published_at=published_at,
        author=doc.author,
        content=doc.text,
        raw_id=url,
    )


def collect(days_back: int, max_results: int) -> list[Article]:
    # The listing page only shows recent posts with no easy pagination
    # (older ones load via a JS "See more" button), so we just take what's
    # there and filter by date - fine for a *weekly* digest.
    candidate_urls = _discover_article_urls(limit=max_results * 2)
    since_ts = datetime.now(tz=timezone.utc).timestamp() - days_back * 86400

    articles = []
    for url in candidate_urls:
        article = _extract_article(url)
        if not article:
            continue
        if article.published_at.timestamp() < since_ts:
            continue
        articles.append(article)
        if len(articles) >= max_results:
            break

    logger.info("anthropic_blog: %d articles collected (last %d days)", len(articles), days_back)
    return articles