import logging
import time
from datetime import datetime, timezone

import feedparser

from models import Article

logger = logging.getLogger(__name__)


def collect_from_feed(feed_url: str, source_name: str, days_back: int, max_results: int) -> list[Article]:
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:
        # Reliability NFR: a broken feed must not take down the whole run.
        logger.warning("Failed to fetch feed '%s' (%s): %s", source_name, feed_url, exc)
        return []

    if not parsed.entries:
        logger.warning("Feed '%s' (%s) returned no entries", source_name, feed_url)
        return []

    since_ts = time.time() - days_back * 86400

    # Some feeds don't guarantee strict chronological order, so we collect
    # everything with a usable date, then sort ourselves before capping.
    dated_entries = []
    for entry in parsed.entries:
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if not time_struct:
            continue
        published_at = datetime.fromtimestamp(time.mktime(time_struct), tz=timezone.utc)
        dated_entries.append((published_at, entry))

    dated_entries.sort(key=lambda pair: pair[0], reverse=True)

    articles = []
    for published_at, entry in dated_entries:
        if published_at.timestamp() < since_ts:
            continue
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue

        articles.append(Article(
            title=title,
            url=link,
            source=source_name,
            published_at=published_at,
            author=entry.get("author"),
            raw_id=entry.get("id") or link,
        ))
        if len(articles) >= max_results:
            break

    logger.info("%s: %d articles collected (last %d days)", source_name, len(articles), days_back)
    return articles