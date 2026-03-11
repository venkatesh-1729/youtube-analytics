"""
YouTube API data fetching for own channel (OAuth).

Handles channel info retrieval, video listing from uploads playlist,
and per-video analytics via the YouTube Analytics API.
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

# Metric query strings for YouTube Analytics API
CORE_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
    "subscribersGained,subscribersLost,likes,dislikes,comments,shares,engagedViews,"
    "videosAddedToPlaylists,videosRemovedFromPlaylists"
)
REACH_METRICS = "videoThumbnailImpressions,videoThumbnailImpressionsClickRate"
ENGAGEMENT_METRICS = (
    "cardImpressions,cardClickRate,"
    "endScreenElementClicks,endScreenElementClickRate"
)

# YouTube Analytics API allows max 200 video IDs per filter
MAX_VIDEOS_PER_QUERY = 200

# Max video IDs per videos.list request (Data API limit)
VIDEOS_LIST_BATCH = 50


# ---------------------------------------------------------------------------
# Channel info
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
    )
    response = _execute_with_retry(response)

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


# ---------------------------------------------------------------------------
# Video listing
# ---------------------------------------------------------------------------

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
        response = _execute_with_retry(request)

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


def fetch_video_details(
    youtube: Any,
    video_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch detailed metadata for videos via the YouTube Data API.

    Retrieves fields not available from playlistItems: duration, tags,
    thumbnail, category, language, topic categories, like/comment counts.

    Args:
        youtube: Authenticated YouTube Data API service.
        video_ids: List of video IDs.

    Returns:
        Dict mapping video_id -> {field: value, ...}.
    """
    details: dict[str, dict[str, Any]] = {}

    for i in range(0, len(video_ids), VIDEOS_LIST_BATCH):
        batch = video_ids[i : i + VIDEOS_LIST_BATCH]

        response = _execute_with_retry(
            youtube.videos().list(
                part="snippet,contentDetails,statistics,topicDetails",
                id=",".join(batch),
            )
        )

        for item in response.get("items", []):
            vid = item.get("id", "")
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content_details = item.get("contentDetails", {})
            topic_details = item.get("topicDetails", {})

            duration_seconds = parse_iso_duration(content_details.get("duration", ""))
            thumbnails = snippet.get("thumbnails", {})
            thumb_url = (
                thumbnails.get("maxres", thumbnails.get("high", {}))
                .get("url", "")
            )

            details[vid] = {
                "duration_seconds": duration_seconds,
                "is_short": duration_seconds <= 60,
                "thumbnail": thumb_url,
                "tags": snippet.get("tags", []),
                "category": snippet.get("categoryId", ""),
                "default_language": snippet.get("defaultLanguage", ""),
                "default_audio_language": snippet.get("defaultAudioLanguage", ""),
                "topic_categories": topic_details.get("topicCategories", []),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "view_count_data_api": int(stats.get("viewCount", 0)),
                "definition": content_details.get("definition", ""),
                "caption": content_details.get("caption", "false") == "true",
                "licensed_content": content_details.get("licensedContent", False),
            }

    logger.info("Fetched details for %d/%d videos", len(details), len(video_ids))
    return details


# ---------------------------------------------------------------------------
# Per-video analytics
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
        row_dict = dict(zip(col_names, row, strict=False))
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
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    all_data: dict[str, dict[str, int | float]] = {}

    for i in range(0, len(video_ids), MAX_VIDEOS_PER_QUERY):
        batch = video_ids[i : i + MAX_VIDEOS_PER_QUERY]
        filter_str = "video==" + ",".join(batch)

        # Core metrics query
        try:
            core_resp = _execute_with_retry(
                analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=today,
                    metrics=CORE_METRICS,
                    dimensions="video",
                    filters=filter_str,
                    sort="-views",
                )
            )
            core_data = _parse_analytics_response(core_resp)
        except Exception as e:
            logger.warning("Core metrics query failed for batch %d: %s", i, e)
            core_data = {}

        # Reach metrics query (impressions/CTR may fail for some video types)
        try:
            reach_resp = _execute_with_retry(
                analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=today,
                    metrics=REACH_METRICS,
                    dimensions="video",
                    filters=filter_str,
                )
            )
            reach_data = _parse_analytics_response(reach_resp)
        except Exception as e:
            logger.debug("Reach metrics query failed (expected for Shorts): %s", e)
            reach_data = {}

        # Engagement metrics (cards, end screens)
        try:
            eng_resp = _execute_with_retry(
                analytics.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=today,
                    metrics=ENGAGEMENT_METRICS,
                    dimensions="video",
                    filters=filter_str,
                )
            )
            eng_data = _parse_analytics_response(eng_resp)
        except Exception as e:
            logger.debug("Engagement metrics query failed: %s", e)
            eng_data = {}

        # Merge all metric sources
        for vid in batch:
            merged: dict[str, int | float] = {}
            if vid in core_data:
                merged.update(core_data[vid])
            if vid in reach_data:
                merged.update(reach_data[vid])
            if vid in eng_data:
                merged.update(eng_data[vid])
            if merged:
                all_data[vid] = merged

        logger.info(
            "Fetched analytics for batch %d-%d (%d/%d videos)",
            i, i + len(batch), len(all_data), len(video_ids),
        )

    return all_data


# ---------------------------------------------------------------------------
# Channel-level analytics
# ---------------------------------------------------------------------------

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
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    def _query_report(
        name: str,
        metrics: str,
        dimensions: str,
        sort: str = "",
        max_results: int | None = None,
        custom_start: str | None = None,
        custom_end: str | None = None,
        filters: str = "",
    ) -> list[dict[str, Any]]:
        """Helper to run an analytics query and return list of dicts."""
        try:
            params: dict[str, Any] = {
                "ids": "channel==MINE",
                "startDate": custom_start or start_date,
                "endDate": custom_end or today,
                "metrics": metrics,
            }
            if dimensions:
                params["dimensions"] = dimensions
            if sort:
                params["sort"] = sort
            if max_results:
                params["maxResults"] = max_results
            if filters:
                params["filters"] = filters

            resp = _execute_with_retry(analytics.reports().query(**params))
            headers = [h["name"] for h in resp.get("columnHeaders", [])]
            return [
                dict(zip(headers, row, strict=False))
                for row in resp.get("rows", [])
            ]
        except Exception as e:
            logger.warning(
                "Channel analytics query '%s' failed: %s", name, e,
            )
            return []

    result: dict[str, Any] = {
        "last_refreshed": datetime.now().isoformat(),
    }

    # Channel overview totals (includes uniqueViewers — channel level only)
    result["channel_totals"] = _query_report(
        "channel_totals",
        (
            "views,estimatedMinutesWatched,subscribersGained,"
            "subscribersLost,likes,dislikes,comments,shares"
        ),
        "",  # no dimensions = aggregate totals
    )

    # Traffic sources
    result["traffic_sources"] = _query_report(
        "traffic_sources",
        "views,estimatedMinutesWatched",
        "insightTrafficSourceType",
        sort="-views",
    )

    # Traffic source details (specific search terms, external URLs)
    # Top search terms
    result["top_search_terms"] = _query_report(
        "top_search_terms",
        "views,estimatedMinutesWatched",
        "insightTrafficSourceDetail",
        sort="-views",
        max_results=25,
        filters="insightTrafficSourceType==YT_SEARCH",
    )

    # Top external sources
    result["top_external_sources"] = _query_report(
        "top_external_sources",
        "views,estimatedMinutesWatched",
        "insightTrafficSourceDetail",
        sort="-views",
        max_results=15,
        filters="insightTrafficSourceType==EXT_URL",
    )

    # Geography (top 25)
    result["top_countries"] = _query_report(
        "top_countries",
        "views,estimatedMinutesWatched,subscribersGained",
        "country",
        sort="-views",
        max_results=25,
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

    # Playback locations (watch page, embedded, mobile app, etc.)
    result["playback_locations"] = _query_report(
        "playback_locations",
        "views,estimatedMinutesWatched",
        "insightPlaybackLocationType",
        sort="-views",
    )

    # Content type breakdown (Shorts vs long-form at channel level)
    result["content_type"] = _query_report(
        "content_type",
        "views,estimatedMinutesWatched,likes,shares,subscribersGained",
        "creatorContentType",
        sort="-views",
    )

    # Demographics (age + gender) — query with views for richer data
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
    thirty_days_ago = (
        datetime.now(tz=UTC) - timedelta(days=30)
    ).strftime("%Y-%m-%d")
    result["daily_trends"] = _query_report(
        "daily_trends",
        (
            "views,subscribersGained,subscribersLost,"
            "estimatedMinutesWatched,likes,shares,comments"
        ),
        "day",
        sort="day",
        custom_start=thirty_days_ago,
    )

    # Monthly trends (full date range, month-aligned start+end)
    # YouTube requires month-aligned dates for month dimension
    from datetime import date as _date

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    month_aligned_start = _date(start_dt.year, start_dt.month, 1)
    today_dt = datetime.now(tz=UTC).date()
    # End = first of current month (last complete month boundary)
    month_aligned_end = _date(today_dt.year, today_dt.month, 1)
    if month_aligned_end > month_aligned_start:
        result["monthly_trends"] = _query_report(
            "monthly_trends",
            (
                "views,subscribersGained,subscribersLost,"
                "estimatedMinutesWatched,likes,shares"
            ),
            "month",
            sort="month",
            custom_start=month_aligned_start.isoformat(),
            custom_end=month_aligned_end.isoformat(),
        )
    else:
        result["monthly_trends"] = []

    if channel_metadata:
        result["channel_metadata"] = channel_metadata

    return result
