"""
YouTube API data fetching for competitor channels (API key).

Provides public data retrieval for competitor analysis using the
YouTube Data API v3 with API-key authentication.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from youtube_analytics.retry import retry_api_call
from youtube_analytics.utils import parse_iso_duration

logger = logging.getLogger(__name__)


@retry_api_call(max_retries=3, base_delay=1.0)
def _execute_with_retry(request: Any) -> Any:
    """Execute a YouTube API request with automatic retry on transient errors."""
    return request.execute()

# Max video IDs per videos.list request
VIDEOS_LIST_BATCH = 50


def fetch_competitor_channel_info(
    youtube: Any,
    channel_id: str,
) -> dict[str, Any]:
    """Fetch public channel info by channel ID.

    Args:
        youtube: YouTube Data API resource (API key auth).
        channel_id: YouTube channel ID (e.g. UC...).

    Returns:
        Dict with title, description, subscriber_count, view_count, video_count,
        uploads_playlist_id, thumbnails.

    Raises:
        ValueError: If channel not found.
    """
    response = _execute_with_retry(
        youtube.channels().list(
            part="snippet,contentDetails,statistics",
            id=channel_id,
        )
    )

    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")

    ch = items[0]
    snippet = ch.get("snippet", {})
    stats = ch.get("statistics", {})
    content_details = ch.get("contentDetails", {})

    return {
        "channel_id": ch.get("id", ""),
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "custom_url": snippet.get("customUrl", ""),
        "published_at": snippet.get("publishedAt", ""),
        "country": snippet.get("country", ""),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "view_count": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "uploads_playlist_id": content_details.get("relatedPlaylists", {}).get("uploads", ""),
        "thumbnails": {
            k: v.get("url", "")
            for k, v in snippet.get("thumbnails", {}).items()
        },
    }


def fetch_competitor_videos(
    youtube: Any,
    channel_id: str,
    months: int = 6,
) -> list[dict[str, Any]]:
    """Fetch recent videos from a competitor channel using the public Data API.

    Gets all videos from the channel's uploads playlist, filters to the last
    N months, and fetches detailed stats for each.

    Args:
        youtube: YouTube Data API resource (API key auth).
        channel_id: YouTube channel ID.
        months: Number of months to look back (default: 6).

    Returns:
        List of video dicts with public metrics, sorted by views descending.
    """
    # Step 1: Get channel info to find uploads playlist
    channel_info = fetch_competitor_channel_info(youtube, channel_id)
    uploads_playlist = channel_info.get("uploads_playlist_id", "")
    if not uploads_playlist:
        logger.warning("No uploads playlist found for channel %s", channel_id)
        return []

    # Step 2: Fetch all video IDs from uploads playlist
    cutoff_date = datetime.now(tz=UTC) - timedelta(days=months * 30)
    all_video_ids: list[dict[str, str]] = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = _execute_with_retry(request)

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            published_at = snippet.get("publishedAt", "")

            if not video_id:
                continue

            # Check if within our time window
            if published_at:
                try:
                    pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if pub_dt < cutoff_date:
                        # Videos are in chronological order; stop if we've gone past cutoff
                        next_page_token = None
                        break
                except ValueError:
                    pass

            all_video_ids.append({"video_id": video_id, "published_at": published_at})

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    logger.info("Found %d videos in last %d months for %s", len(all_video_ids), months, channel_id)

    # Step 3: Fetch detailed stats in batches
    videos: list[dict[str, Any]] = []
    for i in range(0, len(all_video_ids), VIDEOS_LIST_BATCH):
        batch = all_video_ids[i : i + VIDEOS_LIST_BATCH]
        batch_ids = [v["video_id"] for v in batch]

        response = _execute_with_retry(
            youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch_ids),
            )
        )

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            duration_seconds = parse_iso_duration(content_details.get("duration", ""))
            is_short = duration_seconds <= 60

            videos.append({
                "video_id": item.get("id", ""),
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={item.get('id', '')}",
                "published_at": snippet.get("publishedAt", ""),
                "duration_seconds": duration_seconds,
                "is_short": is_short,
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
            })

    # Sort by views descending
    videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)
    logger.info("Fetched details for %d competitor videos", len(videos))
    return videos
