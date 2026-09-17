import logging
import time
from datetime import datetime, timezone

import requests

from models import Article

logger = logging.getLogger(__name__)

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


def _fetch_hits(keyword: str, since_timestamp: int, max_results: int) -> list[dict]:
    """Call the Algolia HN API for a single keyword. Returns raw hit dicts."""
    params = {
        "query": keyword,
        "tags": "story",
        "numericFilters": f"created_at_i>{since_timestamp}",
        "hitsPerPage": max_results,
    }
    response = requests.get(SEARCH_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json().get("hits", [])


def _parse_hit(hit: dict) -> Article | None:
    """Convert one raw Algolia hit into our common Article format."""
    title = hit.get("title")
    url = hit.get("url")
    object_id = hit.get("objectID")

    if not title or not object_id:
        return None

    # Some HN posts (Ask HN / text posts) have no external url - fall back
    # to the HN discussion thread itself so we still have something to link to.
    if not url:
        url = f"https://news.ycombinator.com/item?id={object_id}"

    created_at_i = hit.get("created_at_i")
    published_at = (
        datetime.fromtimestamp(created_at_i, tz=timezone.utc)
        if created_at_i
        else datetime.now(tz=timezone.utc)
    )

    return Article(
        title=title,
        url=url,
        source="hackernews",
        published_at=published_at,
        author=hit.get("author"),
        content=hit.get("story_text"),
        points=hit.get("points"),
        num_comments=hit.get("num_comments"),
        raw_id=object_id,
    )


def collect(keywords: list[str], days_back: int, max_results: int) -> list[Article]:
    """
    Collect recent AI-related stories from Hacker News.

    Runs one search per keyword (Algolia's query matching doesn't reliably
    OR multiple distinct terms), merges results, and de-dupes by HN's own
    objectID - full cross-source deduplication happens in a later step.
    """
    since_timestamp = int(time.time()) - days_back * 86400
    seen_ids: set[str] = set()
    articles: list[Article] = []

    for keyword in keywords:
        try:
            hits = _fetch_hits(keyword, since_timestamp, max_results)
        except requests.RequestException as exc:
            # Reliability NFR: one failing source/keyword must not kill the run.
            logger.warning("Hacker News fetch failed for keyword '%s': %s", keyword, exc)
            continue

        for hit in hits:
            object_id = hit.get("objectID")
            if object_id in seen_ids:
                continue
            article = _parse_hit(hit)
            if article:
                seen_ids.add(object_id)
                articles.append(article)

    logger.info("Hacker News collector: %d unique articles collected", len(articles))
    return articles