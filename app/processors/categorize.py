import logging

logger = logging.getLogger(__name__)

NEWSLETTER_CATEGORIES = [
    "Major Releases",
    "AI Tools",
    "Tutorials",
    "Research",
    "Industry News",
    "Builder's Corner",
]

FALLBACK_CATEGORY = "Industry News"

_NORMALIZED_LOOKUP = {c.strip().lower(): c for c in NEWSLETTER_CATEGORIES}


def normalize_category(raw_category: str) -> str:
    """
    Maps a raw LLM-provided category to one of NEWSLETTER_CATEGORIES,
    tolerating case/whitespace differences. Falls back to a safe default
    - with a log line, so mismatches are visible - rather than ever
    failing the pipeline over a categorization quirk.
    """
    if not raw_category:
        return FALLBACK_CATEGORY

    match = _NORMALIZED_LOOKUP.get(raw_category.strip().lower())
    if match:
        return match

    logger.warning("Unrecognized category '%s' from LLM, falling back to '%s'", raw_category, FALLBACK_CATEGORY)
    return FALLBACK_CATEGORY