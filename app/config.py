"""
Central configuration for the whole pipeline.

Nothing in this project should hardcode an API key, URL, or schedule -
it all comes through here, which reads from a local .env file
(see .env.example for the template). This satisfies the Configurability NFR.

This file will grow in later steps (LLM provider settings, Gmail
credentials, schedule). For now it only has what the Hacker News
collector needs.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Hacker News collector
    hn_keywords: str = "AI,LLM,GPT,machine learning,artificial intelligence"
    hn_days_back: int = 5
    hn_max_results: int = 20

    # OpenAI / Google blog collectors (RSS-based)
    openai_blog_rss_url: str = "https://openai.com/news/rss.xml"
    google_blog_rss_url: str = "https://blog.google/technology/ai/rss/"
    blog_days_back: int = 7
    blog_max_results: int = 20

    # Anthropic blog collector (scraped - no RSS available)
    anthropic_days_back: int = 7
    anthropic_max_results: int = 20

    # YouTube collector (transcripts of recent uploads from selected channels)
    youtube_channels: str = "@AllAboutAI,@mreflow,@TwoMinutePapers"
    youtube_days_back: int = 7
    youtube_max_results_per_channel: int = 10
    transcript_max_chars: int = 8000

    # Content extraction (used across all collectors, not just HN)
    content_max_chars: int = 8000

    # Data cleaning (FR-4)
    min_content_chars: int = 200

    # AI processing (FR-5)
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite" #gemini-3-flash-preview
    gemini_requests_per_minute: int = 10  # conservative default for the free tier

    # Gmail delivery (FR-6)
    gmail_address: str = ""
    gmail_app_password: str = ""
    digest_recipient: str = ""
    
    @property
    def hn_keyword_list(self) -> list[str]:
        return [k.strip() for k in self.hn_keywords.split(",") if k.strip()]

    @property
    def youtube_channel_list(self) -> list[str]:
        return [c.strip() for c in self.youtube_channels.split(",") if c.strip()]


settings = Settings()