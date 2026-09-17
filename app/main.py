import os
import json
import logging
from datetime import datetime, timezone

from models import Article
from config import settings
from processors.clean import clean
from collections import defaultdict
from newsletter.html import generate_html
from processors.deduplicate import deduplicate
from collectors.llm_client import get_llm_client
from newsletter.filter import filter_by_relevance
from processors.summarize import summarize_articles
from collectors.content_extractor import enrich_with_content
from newsletter.email import send, build_subject, EmailError
from collectors import hackernews, openai, google, anthropic, youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CHECKPOINT_FILE = "data_collected.json"   
OUTPUT_FILE = "data_output_sample.json"  
NEWSLETTER_FILE  = "newsletter.html"
 
 
def run_all_collectors() -> list[Article]:
    """
    Run every collector, isolating failures per source
    """
    all_articles: list[Article] = []
 
    collector_calls = [
        # ("hackernews", lambda: hackernews.collect(
        #     keywords=settings.hn_keyword_list,
        #     days_back=settings.hn_days_back,
        #     max_results=settings.hn_max_results,
        # )),
        ("openai_blog", lambda: openai.collect(
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
        ("youtube", lambda: youtube.collect(
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
            logger.error("Collector '%s' failed entirely, skipping it: %s", name, exc)
 
    return all_articles
 
 
def load_checkpoint(path: str) -> list[Article] | None:
    """Returns None if no checkpoint exists yet - that's the signal to run stages 1-3."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = json.load(f)
    return [Article.from_dict(d) for d in raw]
 
 
def save_json(articles: list[Article], path: str):
    with open(path, "w") as f:
        json.dump([a.to_dict() for a in articles], f, indent=2)
 
def load_json(path: str) -> list[Article] | None:
    """Load articles from a JSON file. Returns None if the file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return [Article.from_dict(d) for d in json.load(f)]
    
    
def collect_dedupe_clean() -> list[Article]:
    """Stages 1-3: everything before AI processing."""
    articles = run_all_collectors()
    print(f"\n1. Collected: {len(articles)} articles total")
 
    articles = deduplicate(articles)
    print(f"2. After deduplication: {len(articles)} articles")
 
    to_enrich = [a for a in articles if a.source != "youtube"]
    already_enriched = [a for a in articles if a.source == "youtube"]
    articles = enrich_with_content(to_enrich, max_chars=settings.content_max_chars) + already_enriched
 
    articles = clean(articles)
    print(f"3. After cleaning: {len(articles)} articles")
    return articles
 
def main():
    # Stage 1-3: Collection
    articles = load_json(CHECKPOINT_FILE)
    if articles is not None:
        print(f"[SKIP] Collection  — {CHECKPOINT_FILE} exists ({len(articles)} articles)")
        print(f"       Delete it to re-collect from all sources.\n")
    else:
        print("[RUN]  Collection")
        articles = collect_dedupe_clean()
        save_json(articles, CHECKPOINT_FILE)
        print(f"       Saved → {CHECKPOINT_FILE}\n")
 
    # Stage 4: AI Summary
    analyzed = load_json(OUTPUT_FILE)
    if analyzed is not None:
        print(f"[SKIP] AI analysis — {OUTPUT_FILE} exists ({len(analyzed)} articles)")
        print(f"       Delete it to re-run summarization.\n")
        articles = analyzed
    else:
        print("[RUN]  AI analysis")
        llm_client = get_llm_client(settings)
        articles = summarize_articles(articles, llm_client)
        save_json(articles, OUTPUT_FILE)
        print(f"       {len(articles)} articles analyzed → {OUTPUT_FILE}\n")
 
    # Stage 5: Filter + newsletter
    print("[RUN]  Newsletter generation")
    result = filter_by_relevance(articles)
    kept = result.included
    print(f"       Kept {len(kept)} articles "
          f"({result.discarded_low_score} low-score, "
          f"{result.discarded_thin_summary} thin-summary discarded)")
 
    if not kept:
        print("       No articles passed the filter — newsletter not generated.")
        return
    
    issue_date = datetime.now(tz=timezone.utc)
    html = generate_html(kept, issue_date=datetime.now(tz=timezone.utc))
    with open(NEWSLETTER_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"       Saved → {NEWSLETTER_FILE}\n")
 
    # Summary of what made the cut
    by_cat: dict[str, list] = defaultdict(list)
    for a in kept:
        by_cat[a.category or "Uncategorized"].append(a)
 
    # Stage 6: Email delivery
    print("[RUN]  Email delivery")
    from newsletter.email import send, build_subject, EmailError
    try:
        send(
            html=html,
            subject=build_subject(issue_date),
            from_address=settings.gmail_address,
            app_password=settings.gmail_app_password,
            to_address=settings.digest_recipient or settings.gmail_address,
        )
        recipient = settings.digest_recipient or settings.gmail_address
        print(f"       Sent → {recipient}\n")
    except EmailError as exc:
        print(f"       [WARNING] Email delivery failed: {exc}")
        print(f"       The newsletter was saved to {NEWSLETTER_FILE} and can be opened directly.\n")
 
    # Summary of what made the cut
    by_cat: dict[str, list] = defaultdict(list)
    for a in kept:
        by_cat[a.category or "Uncategorized"].append(a)
 
if __name__ == "__main__":
    main()
