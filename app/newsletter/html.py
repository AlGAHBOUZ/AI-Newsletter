from datetime import datetime, timezone
from collections import defaultdict
import html as html_module

from models import Article
from processors.categorize import NEWSLETTER_CATEGORIES

_SOURCE_LABELS = {
    "hackernews":    "Hacker News",
    "openai_blog":   "OpenAI Blog",
    "google_ai_blog": "Google AI Blog",
    "anthropic_blog": "Anthropic Blog",
    "youtube":       "YouTube",
}


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source.replace("_", " ").title())


def _esc(text: str) -> str:
    return html_module.escape(text or "")


def _article_card(article: Article) -> str:
    source = _source_label(article.source)
    score = article.relevance_score or 0
    date_str = article.published_at.strftime("%d %b %Y").lstrip("0") if article.published_at else ""

    return f"""
    <div class="article-card">
      <div class="article-meta">
        <span class="source-badge">{_esc(source)}</span>
        <span class="article-date">{_esc(date_str)}</span>
      </div>
      <h3 class="article-title">
        <a href="{_esc(article.url)}" target="_blank" rel="noopener">{_esc(article.title)}</a>
      </h3>
      <p class="article-summary">{_esc(article.summary or "")}</p>
      <p class="why-it-matters"><strong>Why it matters:</strong> {_esc(article.why_it_matters or "")}</p>
      <a class="read-more" href="{_esc(article.url)}" target="_blank" rel="noopener">Read the full {"video" if article.source == "youtube" else "article"} →</a>
    </div>"""


def _section(title: str, articles: list[Article], anchor: str = "") -> str:
    if not articles:
        return ""
    anchor_attr = f' id="{anchor}"' if anchor else ""
    cards = "\n".join(_article_card(a) for a in articles)
    return f"""
  <section{anchor_attr}>
    <h2 class="section-title">{_esc(title)}</h2>
    {cards}
  </section>"""


def _executive_summary(top_articles: list[Article]) -> str:
    if not top_articles:
        return ""
    items = ""
    for a in top_articles:
        items += f"""
      <li>
        <a href="{_esc(a.url)}" target="_blank" rel="noopener"><strong>{_esc(a.title)}</strong></a>
        — {_esc(a.summary or "")}
      </li>"""
    return f"""
  <section id="executive-summary">
    <h2 class="section-title">Executive Summary</h2>
    <p class="exec-intro">The week's most significant developments at a glance:</p>
    <ul class="exec-list">{items}
    </ul>
  </section>"""


def _action_items(articles: list[Article]) -> str:
    """High-scoring tools and tutorials worth acting on this week."""
    actionable = [
        a for a in articles
        if (a.relevance_score or 0) >= 8
        and a.category in ("AI Tools", "Tutorials", "Builder's Corner")
    ]
    if not actionable:
        return ""
    items = ""
    for a in actionable:
        items += f"""
      <li>
        <a href="{_esc(a.url)}" target="_blank" rel="noopener"><strong>{_esc(a.title)}</strong></a>
        — {_esc(a.why_it_matters or "")}
      </li>"""
    return f"""
  <section id="action-items">
    <h2 class="section-title">⚡ Action Items</h2>
    <p class="exec-intro">Worth trying or applying this week:</p>
    <ul class="exec-list">{items}
    </ul>
  </section>"""


_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: #f4f5f7;
    color: #1a1a2e;
    font-size: 15px;
    line-height: 1.6;
  }
  .wrapper { max-width: 680px; margin: 32px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }

  /* Header */
  .header { background: #0f0f23; padding: 36px 40px; }
  .header-label { color: #7c8cff; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }
  .header h1 { color: #ffffff; font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }
  .header-date { color: #8888aa; font-size: 13px; margin-top: 6px; }

  /* Nav / TOC */
  .toc { background: #f9f9fc; border-bottom: 1px solid #ebebf0; padding: 16px 40px; display: flex; flex-wrap: wrap; gap: 8px; }
  .toc a { color: #5562d4; font-size: 12px; font-weight: 600; text-decoration: none; background: #eeeeff; padding: 3px 10px; border-radius: 20px; }
  .toc a:hover { background: #dde0ff; }

  /* Sections */
  section { padding: 32px 40px; border-bottom: 1px solid #ebebf0; }
  section:last-child { border-bottom: none; }
  .section-title { font-size: 18px; font-weight: 700; color: #0f0f23; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #7c8cff; display: inline-block; }

  /* Executive Summary & Action Items */
  .exec-intro { color: #555; font-size: 14px; margin-bottom: 12px; }
  .exec-list { padding-left: 20px; }
  .exec-list li { margin-bottom: 12px; font-size: 14px; color: #333; }
  .exec-list a { color: #3d44b5; text-decoration: none; font-weight: 600; }
  .exec-list a:hover { text-decoration: underline; }

  /* Article cards */
  .article-card { margin-bottom: 28px; padding-bottom: 28px; border-bottom: 1px dashed #e0e0ea; }
  .article-card:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .article-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
  .source-badge { background: #eeeeff; color: #5562d4; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 20px; letter-spacing: 0.5px; }
  .article-date { color: #999; font-size: 12px; }
  .score-bar { font-size: 10px; color: #ccc; letter-spacing: -1px; }
  .score-bar { color: #7c8cff; }
  .article-title { font-size: 16px; font-weight: 700; margin-bottom: 8px; line-height: 1.4; }
  .article-title a { color: #0f0f23; text-decoration: none; }
  .article-title a:hover { color: #3d44b5; text-decoration: underline; }
  .article-summary { color: #444; font-size: 14px; margin-bottom: 8px; }
  .why-it-matters { color: #555; font-size: 13px; background: #f4f5ff; border-left: 3px solid #7c8cff; padding: 8px 12px; border-radius: 0 4px 4px 0; margin-bottom: 10px; }
  .read-more { display: inline-block; font-size: 13px; font-weight: 600; color: #3d44b5; text-decoration: none; }
  .read-more:hover { text-decoration: underline; }

  /* Footer */
  .footer { background: #0f0f23; padding: 24px 40px; text-align: center; }
  .footer p { color: #666688; font-size: 12px; line-height: 1.8; }

  /* Responsive */
  @media (max-width: 600px) {
    .wrapper { margin: 0; border-radius: 0; }
    section, .header, .footer, .toc { padding-left: 20px; padding-right: 20px; }
  }
"""


def generate_html(articles: list[Article], issue_date: datetime | None = None) -> str:
    """
    Render the full newsletter as a self-contained HTML string.
    `articles` should already be filtered (only newsletter-worthy ones).
    """
    if issue_date is None:
        issue_date = datetime.now(tz=timezone.utc)

    date_str = issue_date.strftime("%B %d, %Y").replace(" 0", " ")

    # Top 3 by score for Executive Summary
    top3 = sorted(articles, key=lambda a: a.relevance_score or 0, reverse=True)[:3]

    # Group by category, sorted within each category by score desc
    by_category: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        by_category[a.category or "Industry News"].append(a)
    for cat in by_category:
        by_category[cat].sort(key=lambda a: a.relevance_score or 0, reverse=True)

    # Build sections in canonical order
    sections_html = _executive_summary(top3)
    present_categories = [c for c in NEWSLETTER_CATEGORIES if by_category.get(c)]
    for cat in present_categories:
        anchor = cat.lower().replace(" ", "-").replace("'", "")
        sections_html += _section(cat, by_category[cat], anchor=anchor)
    sections_html += _action_items(articles)

    # TOC links
    toc_links = '<a href="#executive-summary">Executive Summary</a>'
    for cat in present_categories:
        anchor = cat.lower().replace(" ", "-").replace("'", "")
        toc_links += f' <a href="#{anchor}">{_esc(cat)}</a>'
    toc_links += ' <a href="#action-items">Action Items</a>'

    total = len(articles)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Weekly Digest — {_esc(date_str)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>AI Weekly Digest</h1>
      <div class="header-date">{_esc(date_str)} &nbsp;·&nbsp; {total} article{"s" if total != 1 else ""}</div>
    </div>
    <nav class="toc">{toc_links}</nav>
    {sections_html}
    <div class="footer">
      <p>AI Weekly Digest &nbsp;·&nbsp; Auto-generated {_esc(date_str)}<br>
      Each summary links directly to the original source.</p>
    </div>
  </div>
</body>
</html>"""