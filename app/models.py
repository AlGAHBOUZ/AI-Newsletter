from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source: str                      # e.g. "hackernews", "openai_blog", "youtube"
    published_at: datetime
    author: Optional[str] = None
    content: Optional[str] = None    # body/snippet text if available
    points: Optional[int] = None     # upvotes/likes, if the source has a notion of it
    num_comments: Optional[int] = None
    raw_id: Optional[str] = None     # source-specific id, useful for dedup/logging

    summary: Optional[str] = None           
    why_it_matters: Optional[str] = None     
    category: Optional[str] = None           
    relevance_score: Optional[int] = None   

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        """
        Inverse of to_dict(). Used to reload a previously-saved checkpoint
        (e.g. data_collected.json) without re-running collection.
        """
        d = dict(d)  # don't mutate the caller's dict
        d["published_at"] = datetime.fromisoformat(d["published_at"])
        return cls(**d)