from app.collectors.hackernews import _parse_hit

SAMPLE_HITS = [
    {
        "created_at": "2026-07-14T10:23:00.000Z",
        "created_at_i": 1752488580,
        "title": "New open-weight AI model released",
        "url": "https://example.com/article",
        "author": "someuser",
        "points": 245,
        "num_comments": 88,
        "objectID": "12345678",
        "story_text": None,
        "_tags": ["story", "author_someuser", "story_12345678"],
    },
    {
        # Ask HN style post: no external url
        "created_at": "2026-07-15T08:00:00.000Z",
        "created_at_i": 1752566400,
        "title": "Ask HN: How are you using LLMs day to day?",
        "url": None,
        "author": "otheruser",
        "points": 40,
        "num_comments": 12,
        "objectID": "87654321",
        "story_text": "Curious what workflows people have built...",
        "_tags": ["story", "ask_hn", "author_otheruser"],
    },
    {
        # Broken/invalid entry - should be dropped
        "created_at": "2026-07-15T09:00:00.000Z",
        "created_at_i": 1752570000,
        "title": None,
        "url": "https://example.com/broken",
        "author": "ghost",
        "points": 1,
        "num_comments": 0,
        "objectID": None,
    },
]


def test_parse_hit():
    results = [a for hit in SAMPLE_HITS if (a := _parse_hit(hit)) is not None]

    assert len(results) == 2

    first = results[0]
    assert first.title == "New open-weight AI model released"
    assert first.url == "https://example.com/article"
    assert first.source == "hackernews"
    assert first.points == 245

    second = results[1]
    assert second.url == "https://news.ycombinator.com/item?id=87654321"