from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.collectors.youtube import _parse_upload_date, collect

NOW = datetime.now(tz=timezone.utc)


def test_parse_upload_date():
    assert _parse_upload_date("20260715") == datetime(2026, 7, 15, tzinfo=timezone.utc)
    assert _parse_upload_date(None) is None
    assert _parse_upload_date("not-a-date") is None
    print("_parse_upload_date: all cases passed")


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def test_collect_orchestration():
    # Channel A: 4 videos, newest-first, where the 3rd is outside a 7-day
    # window - collect() should stop there and never "fetch details" for
    # the 4th, even though it's in the returned ID list.
    channel_a_ids = ["vid1", "vid2", "vid3_old", "vid4_never_checked"]
    details_by_id = {
        "vid1": {"title": "Newest video", "upload_date": _fmt(NOW - timedelta(days=1)), "uploader": "Channel A"},
        "vid2": {"title": "Second video", "upload_date": _fmt(NOW - timedelta(days=3)), "uploader": "Channel A"},
        "vid3_old": {"title": "Too old", "upload_date": _fmt(NOW - timedelta(days=30)), "uploader": "Channel A"},
        "vid4_never_checked": {"title": "Should never be fetched", "upload_date": _fmt(NOW), "uploader": "Channel A"},
    }
    fetched_ids = []

    def fake_list_ids(handle, limit):
        if handle == "@ChannelA":
            return channel_a_ids
        if handle == "@BrokenChannel":
            return []  # simulates yt-dlp failing and _list_recent_video_ids catching it
        raise AssertionError(f"unexpected handle {handle}")

    def fake_fetch_details(video_id):
        fetched_ids.append(video_id)
        return details_by_id.get(video_id)

    def fake_fetch_transcript(video_id, max_chars):
        return f"transcript for {video_id}"

    with patch("collectors.youtube._list_recent_video_ids", side_effect=fake_list_ids), \
         patch("collectors.youtube._fetch_video_details", side_effect=fake_fetch_details), \
         patch("collectors.youtube._fetch_transcript_text", side_effect=fake_fetch_transcript):

        articles = collect(
            channel_handles=["@ChannelA", "@BrokenChannel"],
            days_back=7,
            max_results_per_channel=10,
            transcript_max_chars=8000,
        )

    assert len(articles) == 2, f"expected 2 in-window videos from Channel A, got {len(articles)}: {[a.title for a in articles]}"
    assert "vid4_never_checked" not in fetched_ids, (
        "collect() should stop fetching details once it hits an out-of-window video, "
        "not keep going through the rest of the (newest-first) list"
    )
    assert articles[0].content == "transcript for vid1"
    assert articles[0].author == "Channel A"

    # A channel that fails to list videos entirely must not crash the run
    # or affect the other channel's results (Reliability NFR).
    print("collect() orchestration: early-stop, cap, and channel-failure isolation all passed")

    # max_results_per_channel cap, independent of the date window
    fetched_ids.clear()
    with patch("collectors.youtube._list_recent_video_ids", side_effect=fake_list_ids), \
         patch("collectors.youtube._fetch_video_details", side_effect=fake_fetch_details), \
         patch("collectors.youtube._fetch_transcript_text", side_effect=fake_fetch_transcript):

        capped = collect(
            channel_handles=["@ChannelA"],
            days_back=365,  # wide enough that the date window isn't the limiting factor
            max_results_per_channel=1,
            transcript_max_chars=8000,
        )
    assert len(capped) == 1, f"expected max_results_per_channel to cap at 1, got {len(capped)}"
    print("collect() max_results_per_channel cap: passed")


if __name__ == "__main__":
    test_parse_upload_date()
    test_collect_orchestration()
    print("All youtube collector offline tests passed.")