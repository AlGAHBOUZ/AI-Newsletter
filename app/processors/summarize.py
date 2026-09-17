import logging
from typing import Literal

from pydantic import BaseModel, Field

from collectors.llm_client import LLMClient, LLMError
from models import Article
from processors.categorize import NEWSLETTER_CATEGORIES, normalize_category

logger = logging.getLogger(__name__)

_Category = Literal[tuple(NEWSLETTER_CATEGORIES)]


class ArticleAnalysis(BaseModel):
    summary: str = Field(description="2-4 sentences: what actually happened, in plain language, in your own words.")
    why_it_matters: str = Field(
        description="1-2 sentences: the practical significance for someone trying to stay current on AI - "
        "not generic hype, the actual implication."
    )
    category: _Category = Field(description="Which newsletter section this article belongs in.")
    relevance_score: int = Field(
        ge=1, le=10,
        description="1-10: how newsletter-worthy this is. See the scoring guide in the prompt.",
    )


_SYSTEM_PROMPT = """\
You are the editorial assistant for a weekly AI newsletter. The reader is a busy person \
who wants to stay current on real developments in AI without reading every article, blog \
post, and video themselves. Your job on each item is to give them exactly what they'd want \
to know if they only had one sentence of your attention, plus one more sentence on why it's \
worth their time (or isn't).

Rules:
- Write the summary and "why it matters" entirely in your own words. Do not copy phrasing \
from the source text, even short distinctive phrases.
- Be concrete. "This is a significant advancement" is not useful; "this cuts inference cost \
by 40% for long-context tasks" is.
- Skip marketing language from the source (e.g. "revolutionary", "game-changing") unless \
you're explicitly noting that the source itself is being promotional.
- If the content is thin, off-topic, or you can't tell what actually happened, still fill in \
best-effort fields, but give it a low relevance_score - don't inflate importance to compensate \
for thin material.

Relevance score guide (1-10):
- 9-10: A major model/product release, a significant capability jump, or news that changes \
how people build with or think about AI.
- 6-8: A meaningful but incremental update, a genuinely useful tool or tutorial, solid research \
with real implications.
- 3-5: Minor updates, niche tooling, commentary/opinion pieces, routine industry news.
- 1-2: Barely AI-relevant, very niche, or content with little substance beyond a headline.
"""


def build_prompt(article: Article) -> str:

    content = article.content or "(no content available)"
    return (
        f"Source: {article.source}\n"
        f"Title: {article.title}\n"
        f"Published: {article.published_at.date().isoformat()}\n"
        f"URL: {article.url}\n\n"
        f"Content:\n{content}"
    )


def analyze_article(article: Article, client: LLMClient) -> ArticleAnalysis | None:
    """Returns None (and logs) on failure - one bad article must not stop the batch."""
    try:
        return client.generate_json(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=build_prompt(article),
            schema=ArticleAnalysis,
        )
    except LLMError as exc:
        logger.warning("Analysis failed for '%s': %s", article.title, exc)
        return None


def summarize_articles(articles: list[Article], client: LLMClient) -> list[Article]:
    """
    Runs analyze_article on every article, writing successful results back
    onto the Article's summary/why_it_matters/category/relevance_score
    fields. Articles that fail analysis are dropped (Reliability NFR) -
    an article with no summary can't go in the newsletter anyway, so
    there's no reason to carry it further through the pipeline.
    """
    processed: list[Article] = []
    failed = 0

    for article in articles:
        analysis = analyze_article(article, client)
        if analysis is None:
            failed += 1
            continue

        article.summary = analysis.summary
        article.why_it_matters = analysis.why_it_matters
        article.category = normalize_category(analysis.category)
        article.relevance_score = analysis.relevance_score
        processed.append(article)

    logger.info("AI processing: %d articles analyzed, %d failed", len(processed), failed)
    return processed