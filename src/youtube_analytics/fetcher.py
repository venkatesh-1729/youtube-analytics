"""
YouTube API data fetching for own and competitor channels.

Own channel (OAuth): full analytics via YouTube Analytics API.
Competitor channel (API key): public data via YouTube Data API.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Metric query strings for YouTube Analytics API
CORE_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
    "subscribersGained,subscribersLost,likes,dislikes,comments,shares,engagedViews,"
    "videosAddedToPlaylists,videosRemovedFromPlaylists"
)
REACH_METRICS = "videoThumbnailImpressions,videoThumbnailImpressionsClickRate"

# YouTube Analytics API allows max 200 video IDs per filter
MAX_VIDEOS_PER_QUERY = 200

# Max video IDs per videos.list request
VIDEOS_LIST_BATCH = 50

# Delay between transcript fetches to avoid rate limiting
TRANSCRIPT_FETCH_DELAY = 1.0


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def get_video_id(url: str) -> str:
    """Extract video ID from a YouTube URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def _parse_iso_duration(duration: str) -> int:
    """Parse ISO 8601 duration (e.g. PT1M30S) to total seconds.

    Args:
        duration: ISO 8601 duration string from contentDetails.duration.

    Returns:
        Total seconds. Returns 0 if parse fails.
    """
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


# ---------------------------------------------------------------------------
# Own channel: YouTube Data API (OAuth)
# ---------------------------------------------------------------------------

def get_channel_info(youtube: Any) -> tuple[str, str, str, dict[str, Any]]:
    """Get the authenticated user's channel info and metadata.

    Args:
        youtube: Authenticated YouTube Data API service.

    Returns:
        Tuple of (channel_title, start_date_YYYY_MM_DD, uploads_playlist_id, channel_metadata).
        channel_metadata includes subscriber_count, view_count, video_count, etc.
    """
    response = youtube.channels().list(
        part="snippet,contentDetails,statistics,topicDetails,status,brandingSettings",
        mine=True,
    ).execute()

    if not response.get("items"):
        raise ValueError("No channel found for the authenticated account.")

    ch = response["items"][0]
    snippet = ch.get("snippet", {})
    stats = ch.get("statistics", {})
    content_details = ch.get("contentDetails", {})
    topic_details = ch.get("topicDetails", {})
    status = ch.get("status", {})

    published = snippet.get("publishedAt", "2020-01-01T00:00:00Z")
    start_date = published[:10]

    uploads_playlist = content_details.get("relatedPlaylists", {}).get("uploads", "")

    channel_metadata = {
        "channel_id": ch.get("id", ""),
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "custom_url": snippet.get("customUrl", ""),
        "published_at": published,
        "country": snippet.get("country", ""),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
        "view_count": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "keywords": ch.get("brandingSettings", {}).get("channel", {}).get("keywords", ""),
        "topic_categories": topic_details.get("topicCategories", []),
        "thumbnails": {
            k: v.get("url", "")
            for k, v in snippet.get("thumbnails", {}).items()
        },
        "privacy_status": status.get("privacyStatus", ""),
        "is_linked": status.get("isLinked", False),
        "long_uploads_status": status.get("longUploadsStatus", ""),
        "made_for_kids": status.get("madeForKids", False),
        "self_declared_made_for_kids": status.get("selfDeclaredMadeForKids", False),
        "unsubscribed_trailer": content_details.get("relatedPlaylists", {}).get(
            "unsubscribedTrailer", ""
        ),
    }

    return snippet.get("title", ""), start_date, uploads_playlist, channel_metadata


def fetch_all_channel_videos(
    youtube: Any,
    uploads_playlist_id: str,
) -> list[dict[str, Any]]:
    """Fetch all videos from the channel's uploads playlist.

    Args:
        youtube: Authenticated YouTube Data API service.
        uploads_playlist_id: The channel's uploads playlist ID.

    Returns:
        List of video dicts with video_id, url, title, description, published_at.
    """
    videos: list[dict[str, Any]] = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            if not video_id:
                continue

            videos.append({
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "published_at": snippet.get("publishedAt", ""),
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    logger.info("Fetched %d videos from uploads playlist", len(videos))
    return videos


# ---------------------------------------------------------------------------
# Own channel: YouTube Analytics API (OAuth)
# ---------------------------------------------------------------------------

def _parse_analytics_response(
    response: dict[str, Any],
) -> dict[str, dict[str, int | float]]:
    """Parse YouTube Analytics API response into video_id -> metrics dict.

    Handles dynamic column order from columnHeaders.
    """
    headers = response.get("columnHeaders", [])
    rows = response.get("rows", [])

    if not headers or not rows:
        return {}

    col_names = [h["name"] for h in headers]
    result: dict[str, dict[str, int | float]] = {}

    for row in rows:
        row_dict = dict(zip(col_names, row))
        vid = row_dict.pop("video", "")
        if vid:
            result[vid] = row_dict

    return result


def fetch_analytics_per_video(
    analytics: Any,
    video_ids: list[str],
    start_date: str,
) -> dict[str, dict[str, int | float]]:
    """Fetch comprehensive analytics per video from YouTube Analytics API.

    Fetches core metrics (views, watch time, retention, engagement, subscribers)
    and reach metrics (impressions, CTR). Batches requests at 200 videos per query.

    Args:
        analytics: Authenticated YouTube Analytics service.
        video_ids: List of video IDs to fetch analytics for.
        start_date: Start date in YYYY-MM-DD format.

    Returns:
        Dict mapping video_id -> {metric_name: value, ...}.
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    all_data: dict[str, dict[str, int | float]] = {}

    for i in range(0, len(video_ids), MAX_VIDEOS_PER_QUERY):
        batch = video_ids[i : i + MAX_VIDEOS_PER_QUERY]
        filter_str = "video==" + ",".join(batch)

        # Core metrics query
        try:
            core_resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=today,
                metrics=CORE_METRICS,
                dimensions="video",
                filters=filter_str,
                sort="-views",
            ).execute()
            core_data = _parse_analytics_response(core_resp)
        except Exception as e:
            logger.warning("Core metrics query failed for batch %d: %s", i, e)
            core_data = {}

        # Reach metrics query (impressions/CTR may fail for some video types)
        try:
            reach_resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=today,
                metrics=REACH_METRICS,
                dimensions="video",
                filters=filter_str,
            ).execute()
            reach_data = _parse_analytics_response(reach_resp)
        except Exception as e:
            logger.debug("Reach metrics query failed (expected for Shorts): %s", e)
            reach_data = {}

        # Merge core + reach
        for vid in batch:
            merged: dict[str, int | float] = {}
            if vid in core_data:
                merged.update(core_data[vid])
            if vid in reach_data:
                merged.update(reach_data[vid])
            if merged:
                all_data[vid] = merged

        logger.info(
            "Fetched analytics for batch %d-%d (%d/%d videos)",
            i, i + len(batch), len(all_data), len(video_ids),
        )

    return all_data


def fetch_channel_level_analytics(
    analytics: Any,
    start_date: str,
    channel_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch channel-level analytics: traffic sources, geography, devices, demographics.

    Args:
        analytics: Authenticated YouTube Analytics service.
        start_date: Start date in YYYY-MM-DD format.
        channel_metadata: Optional channel metadata to include in output.

    Returns:
        Dict with traffic_sources, top_countries, subscribed_breakdown,
        device_types, operating_systems, demographics, sharing_services, daily_trends.
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    def _query_report(
        name: str,
        metrics: str,
        dimensions: str,
        sort: str = "",
        max_results: int | None = None,
        custom_start: str | None = None,
    ) -> list[dict[str, Any]]:
        """Helper to run an analytics query and return list of dicts."""
        try:
            params: dict[str, Any] = {
                "ids": "channel==MINE",
                "startDate": custom_start or start_date,
                "endDate": today,
                "metrics": metrics,
                "dimensions": dimensions,
            }
            if sort:
                params["sort"] = sort
            if max_results:
                params["maxResults"] = max_results

            resp = analytics.reports().query(**params).execute()
            headers = [h["name"] for h in resp.get("columnHeaders", [])]
            return [dict(zip(headers, row)) for row in resp.get("rows", [])]
        except Exception as e:
            logger.warning("Channel analytics query '%s' failed: %s", name, e)
            return []

    result: dict[str, Any] = {
        "last_refreshed": datetime.now().isoformat(),
    }

    # Traffic sources
    result["traffic_sources"] = _query_report(
        "traffic_sources",
        "views,estimatedMinutesWatched",
        "insightTrafficSourceType",
        sort="-views",
    )

    # Geography (top 15)
    result["top_countries"] = _query_report(
        "top_countries",
        "views,estimatedMinutesWatched,subscribersGained",
        "country",
        sort="-views",
        max_results=15,
    )

    # Subscribed vs unsubscribed
    result["subscribed_breakdown"] = _query_report(
        "subscribed_breakdown",
        "views,estimatedMinutesWatched",
        "subscribedStatus",
    )

    # Device types
    result["device_types"] = _query_report(
        "device_types",
        "views,estimatedMinutesWatched",
        "deviceType",
        sort="-views",
    )

    # Operating systems
    result["operating_systems"] = _query_report(
        "operating_systems",
        "views,estimatedMinutesWatched",
        "operatingSystem",
        sort="-views",
    )

    # Demographics (age + gender)
    result["demographics"] = _query_report(
        "demographics",
        "viewerPercentage",
        "ageGroup,gender",
    )

    # Sharing services
    result["sharing_services"] = _query_report(
        "sharing_services",
        "shares",
        "sharingService",
        sort="-shares",
        max_results=15,
    )

    # Daily trends (last 30 days for recency)
    thirty_days_ago = (datetime.now(tz=timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    result["daily_trends"] = _query_report(
        "daily_trends",
        "views,subscribersGained,subscribersLost,estimatedMinutesWatched",
        "day",
        sort="day",
        custom_start=thirty_days_ago,
    )

    if channel_metadata:
        result["channel_metadata"] = channel_metadata

    return result


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

def fetch_transcript(video_id: str) -> str:
    """Fetch transcript for a single video using youtube-transcript-api.

    No auth required. Returns plain text; empty string if unavailable.
    Supports both v0.x (class methods) and v1.x (instance methods) APIs.

    Args:
        video_id: YouTube video ID.

    Returns:
        Transcript text, or empty string if fetch fails.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.warning("youtube-transcript-api not installed; skipping transcript fetch")
        return ""

    # Preferred languages: Telugu first, then English
    languages = ["te", "en"]

    try:
        # v1.x API: instance-based with .fetch() and .list()
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=languages)
        # transcript is a FetchedTranscript with snippet objects
        return " ".join(
            snippet.text for snippet in transcript if snippet.text
        )
    except TypeError:
        # v0.x fallback: class method API
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except Exception:
                transcript = transcript_list.find_generated_transcript(languages)

            if transcript:
                entries = transcript.fetch()
                return " ".join(e.get("text", "") for e in entries if e.get("text"))
        except Exception as e:
            logger.debug("Transcript not available for %s: %s", video_id, e)
    except Exception as e:
        logger.debug("Transcript not available for %s: %s", video_id, e)

    return ""


def fetch_transcripts_for_videos(
    video_ids: list[str],
    delay_seconds: float = TRANSCRIPT_FETCH_DELAY,
) -> dict[str, str]:
    """Fetch transcripts for multiple videos.

    Args:
        video_ids: List of YouTube video IDs.
        delay_seconds: Seconds to wait between fetches.

    Returns:
        Dict mapping video_id -> transcript text. Missing/failed videos omitted.
    """
    transcripts: dict[str, str] = {}
    for i, vid in enumerate(video_ids):
        text = fetch_transcript(vid)
        if text:
            transcripts[vid] = text
        if i < len(video_ids) - 1:
            time.sleep(delay_seconds)

    logger.info("Fetched transcripts for %d/%d videos", len(transcripts), len(video_ids))
    return transcripts


# ---------------------------------------------------------------------------
# Competitor channel: YouTube Data API (API key)
# ---------------------------------------------------------------------------

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
    response = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id,
    ).execute()

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
    cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=months * 30)
    all_video_ids: list[dict[str, str]] = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = request.execute()

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

        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(batch_ids),
        ).execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            duration_seconds = _parse_iso_duration(content_details.get("duration", ""))
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
