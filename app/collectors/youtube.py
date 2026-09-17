import logging
from datetime import datetime, timezone

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from models import Article

logger = logging.getLogger(__name__)


def _list_recent_video_ids(channel_handle: str, limit: int) -> list[str]:
    """Cheap flat listing: just video IDs, newest first, no per-video fetch."""
    channel_url = f"https://www.youtube.com/{channel_handle}/videos"
    ydl_opts = {
        "extract_flat": True,
        "playlistend": limit,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    except Exception as exc:
        logger.warning("Failed to list videos for channel %s: %s", channel_handle, exc)
        return []

    entries = (info or {}).get("entries") or []
    return [e["id"] for e in entries if e and e.get("id")]


def _fetch_video_details(video_id: str) -> dict | None:
    """Full metadata for one video: title, upload_date, uploader, etc."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.info("Could not fetch details for video %s: %s", video_id, exc)
        return None


def _parse_upload_date(upload_date: str | None) -> datetime | None:
    """yt-dlp gives upload_date as 'YYYYMMDD'."""
    if not upload_date:
        return None
    try:
        return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fetch_transcript_text(video_id: str, max_chars: int) -> str | None:
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join(snippet.text for snippet in transcript)
        return text[:max_chars] if text else None
    except Exception as exc:
        # Very common and expected: captions disabled, auto-captions not
        # generated yet, or the video is members-only. Not a pipeline failure.
        logger.info("No transcript available for video %s: %s", video_id, exc)
        return None


def collect(
    channel_handles: list[str],
    days_back: int,
    max_results_per_channel: int,
    transcript_max_chars: int,
) -> list[Article]:
    all_videos: list[Article] = []
    since_ts = datetime.now(tz=timezone.utc).timestamp() - days_back * 86400

    for handle in channel_handles:
        # Ask for a few extra IDs beyond max_results, since some will be
        # filtered out by date and we'd rather not undershoot.
        video_ids = _list_recent_video_ids(handle, limit=max_results_per_channel * 2)
        if not video_ids:
            logger.warning("No videos found (or channel unreachable) for %s", handle)
            continue

        collected_for_channel = 0
        for video_id in video_ids:
            details = _fetch_video_details(video_id)
            if not details or not details.get("title"):
                continue

            published_at = _parse_upload_date(details.get("upload_date"))
            if published_at is None:
                published_at = datetime.now(tz=timezone.utc)  # unknown date - don't silently drop it
            elif published_at.timestamp() < since_ts:
                # Newest-first listing: once we're past the window, every
                # remaining video for this channel is even older. Stop early.
                break

            article = Article(
                title=details["title"],
                url=f"https://www.youtube.com/watch?v={video_id}",
                source="youtube",
                published_at=published_at,
                author=details.get("uploader") or handle,
                raw_id=video_id,
            )
            article.content = _fetch_transcript_text(video_id, max_chars=transcript_max_chars)
            all_videos.append(article)

            collected_for_channel += 1
            if collected_for_channel >= max_results_per_channel:
                break

        logger.info("youtube (%s): %d videos within last %d days", handle, collected_for_channel, days_back)

    return all_videos