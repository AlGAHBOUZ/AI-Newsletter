from config import settings
from models import Article
from modules import collect_from_feed


def collect(days_back: int, max_results: int) -> list[Article]:
    return collect_from_feed(
        feed_url=settings.openai_blog_rss_url,
        source_name="openai_blog",
        days_back=days_back,
        max_results=max_results,
    )