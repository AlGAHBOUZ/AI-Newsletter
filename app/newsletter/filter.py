import logging
from dataclasses import dataclass

from models import Article

logger = logging.getLogger(__name__)

MIN_SCORE_TO_INCLUDE = 5
BORDERLINE_SCORE_MAX = 6
MIN_SUMMARY_CHARS_FOR_BORDERLINE = 60


@dataclass
class FilterResult:
    included: list[Article]
    discarded_low_score: int
    discarded_thin_summary: int


def filter_by_relevance(articles: list[Article]) -> FilterResult:
    """
    Split articles into newsletter-worthy and discarded.
    Articles that were never analyzed (no score) are treated as score=0 and discarded.
    """
    included: list[Article] = []
    discarded_low = 0
    discarded_thin = 0

    for article in articles:
        score = article.relevance_score or 0

        if score < MIN_SCORE_TO_INCLUDE:
            discarded_low += 1
            logger.debug("Discarded (score %d): %s", score, article.title)
            continue

        if score <= BORDERLINE_SCORE_MAX:
            summary_len = len(article.summary or "")
            if summary_len < MIN_SUMMARY_CHARS_FOR_BORDERLINE:
                discarded_thin += 1
                logger.info(
                    "Discarded borderline (score %d, summary %d chars): %s",
                    score, summary_len, article.title,
                )
                continue

        included.append(article)

    logger.info(
        "Filter: %d included, %d discarded (low score), %d discarded (thin summary)",
        len(included), discarded_low, discarded_thin,
    )
    return FilterResult(
        included=included,
        discarded_low_score=discarded_low,
        discarded_thin_summary=discarded_thin,
    )