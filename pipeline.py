import json
import logging
import os
from datetime import datetime, timezone

from app.config import settings
from app.collectors import hackernews, openai, google, anthropic, youtube
from app.collectors.content_extractor import enrich_with_content
from app.processors.deduplicate import deduplicate
from app.processors.clean import clean
from app.processors.summarize import summarize_articles
from app.newsletter.filter import filter_by_relevance
from app.newsletter.html import generate_html
from app.newsletter.email import send, build_subject, EmailError
from app.collectors.llm_client import get_llm_client
from app.models import Article

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", ".")  # override on Render via env var


def _today_cache_path() -> str:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(DATA_DIR, f"data_{today}.json")


def _load_cache(path: str) -> list[Article] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return [Article.from_dict(d) for d in json.load(f)]
    except Exception as exc:
        logger.warning("Failed to load cache %s: %s — will re-run pipeline", path, exc)
        return None


def _save_cache(articles: list[Article], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump([a.to_dict() for a in articles], f, indent=2)


def _run_full_pipeline() -> list[Article]:
    """Collect, dedup, enrich, clean, and AI-analyze. Returns analyzed articles."""
    logger.info("Starting full pipeline run")

    # 1-3: Collection
    all_articles: list[Article] = []
    collector_calls = [
        ("hackernews",    lambda: hackernews.collect(
            keywords=settings.hn_keyword_list,
            days_back=settings.hn_days_back,
            max_results=settings.hn_max_results,
        )),
        ("openai_blog",   lambda: openai.collect(
            days_back=settings.blog_days_back,
            max_results=settings.blog_max_results,
        )),
        ("google_ai_blog", lambda: google.collect(
            days_back=settings.blog_days_back,
            max_results=settings.blog_max_results,
        )),
        ("anthropic_blog", lambda: anthropic.collect(
            days_back=settings.anthropic_days_back,
            max_results=settings.anthropic_max_results,
        )),
        ("youtube",       lambda: youtube.collect(
            channel_handles=settings.youtube_channel_list,
            days_back=settings.youtube_days_back,
            max_results_per_channel=settings.youtube_max_results_per_channel,
            transcript_max_chars=settings.transcript_max_chars,
        )),
    ]
    for name, call in collector_calls:
        try:
            articles = call()
            logger.info("%s: %d articles", name, len(articles))
            all_articles.extend(articles)
        except Exception as exc:
            logger.error("Collector '%s' failed, skipping: %s", name, exc)

    # Dedup + enrich + clean
    all_articles = deduplicate(all_articles)
    to_enrich = [a for a in all_articles if a.source != "youtube"]
    enriched_yt = [a for a in all_articles if a.source == "youtube"]
    all_articles = enrich_with_content(to_enrich, max_chars=settings.content_max_chars) + enriched_yt
    all_articles = clean(all_articles)
    logger.info("After collection + cleaning: %d articles", len(all_articles))

    # 4: AI analysis
    llm_client = get_llm_client(settings)
    all_articles = summarize_articles(all_articles, llm_client)
    logger.info("After AI analysis: %d articles", len(all_articles))

    return all_articles


def run_and_deliver(to_email: str) -> dict:
    """
    Main entry point called by both Flask and CLI.

    Returns a result dict:
      {"ok": True,  "articles": N, "cached": bool}
      {"ok": False, "error": "message"}
    """
    cache_path = _today_cache_path()

    # Load today's cache or run the full pipeline
    articles = _load_cache(cache_path)
    if articles is not None:
        logger.info("Using today's cache (%s): %d articles", cache_path, len(articles))
        cached = True
    else:
        logger.info("No cache found — running full pipeline")
        try:
            articles = _run_full_pipeline()
        except Exception as exc:
            logger.exception("Pipeline failed")
            return {"ok": False, "error": f"Pipeline error: {exc}"}
        _save_cache(articles, cache_path)
        cached = False

    # Filter + render
    result = filter_by_relevance(articles)
    kept = result.included
    logger.info("Filter: %d kept, %d dropped", len(kept), result.discarded_low_score)

    if not kept:
        return {"ok": False, "error": "No articles passed the relevance filter this week."}

    issue_date = datetime.now(tz=timezone.utc)
    html = generate_html(kept, issue_date=issue_date)

    # Deliver
    try:
        send(
            html=html,
            subject=build_subject(issue_date),
            from_address=settings.gmail_address,
            app_password=settings.gmail_app_password,
            to_address=to_email,
        )
    except EmailError as exc:
        logger.error("Email delivery failed for %s: %s", to_email, exc)
        return {"ok": False, "error": str(exc)}

    logger.info("Newsletter delivered to %s (cached=%s)", to_email, cached)
    return {"ok": True, "articles": len(kept), "cached": cached}