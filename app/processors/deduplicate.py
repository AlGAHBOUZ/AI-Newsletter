import logging
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from models import Article

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parts.query)))
    return urlunsplit(("", netloc, path, query, ""))


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title).strip().lower()


def deduplicate(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()  # (source, normalized_title)
    unique: list[Article] = []
    dropped = 0

    for article in articles:
        url_key = _normalize_url(article.url)
        title_key = (article.source, _normalize_title(article.title))

        if url_key in seen_urls or title_key in seen_titles:
            dropped += 1
            continue

        seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(article)

    if dropped:
        logger.info("Deduplication: dropped %d duplicate articles", dropped)

    return unique