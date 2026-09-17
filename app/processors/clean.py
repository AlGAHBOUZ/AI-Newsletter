import logging

from config import settings
from models import Article

logger = logging.getLogger(__name__)


def is_valid(article: Article) -> bool:
    if not article.title or not article.title.strip():
        return False
    if not article.url or not article.url.startswith("http"):
        return False
    if not article.source:
        return False
    return True


def has_content(article: Article) -> bool:
    return bool(article.content) and len(article.content.strip()) >= settings.min_content_chars


def clean(articles: list[Article]) -> list[Article]:
    valid = [a for a in articles if is_valid(a)]
    dropped_invalid = len(articles) - len(valid)

    with_content = [a for a in valid if has_content(a)]
    dropped_empty = len(valid) - len(with_content)

    if dropped_invalid:
        logger.info("Cleaning: dropped %d invalid entries", dropped_invalid)
    if dropped_empty:
        logger.info("Cleaning: dropped %d articles with empty/too-short content", dropped_empty)

    return with_content