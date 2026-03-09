"""
Data persistence for YouTube channel analytics.

Handles loading and saving metadata.json, channel_analytics.json, and
channel_info.json. All functions accept a channel_dir Path, making the
module repo-agnostic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Map YouTube Analytics API metric names to our snake_case field names
METRIC_TO_FIELD: dict[str, str] = {
    "views": "views",
    "estimatedMinutesWatched": "estimated_minutes_watched",
    "averageViewDuration": "average_view_duration_seconds",
    "averageViewPercentage": "average_view_percentage",
    "subscribersGained": "subscribers_gained",
    "subscribersLost": "subscribers_lost",
    "likes": "likes",
    "dislikes": "dislikes",
    "comments": "comments",
    "shares": "shares",
    "engagedViews": "engaged_views",
    "videosAddedToPlaylists": "videos_added_to_playlists",
    "videosRemovedFromPlaylists": "videos_removed_from_playlists",
    "videoThumbnailImpressions": "thumbnail_impressions",
    "videoThumbnailImpressionsClickRate": "thumbnail_ctr_percentage",
}


def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from a URL."""
    import re

    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


# ---------------------------------------------------------------------------
# Load / Save helpers
# ---------------------------------------------------------------------------


def load_metadata(channel_dir: Path) -> list[dict[str, Any]]:
    """Load video metadata from a channel's metadata.json.

    Args:
        channel_dir: Path to the channel directory.

    Returns:
        List of video dicts, or empty list if file doesn't exist.
    """
    metadata_file = Path(channel_dir) / "metadata.json"
    if not metadata_file.exists():
        return []
    return json.loads(metadata_file.read_text(encoding="utf-8"))


def save_metadata(channel_dir: Path, data: list[dict[str, Any]]) -> Path:
    """Save video metadata to a channel's metadata.json.

    Args:
        channel_dir: Path to the channel directory.
        data: List of video dicts to save.

    Returns:
        Path to the saved file.
    """
    channel_path = Path(channel_dir)
    channel_path.mkdir(parents=True, exist_ok=True)
    metadata_file = channel_path / "metadata.json"
    metadata_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved %d videos to %s", len(data), metadata_file)
    return metadata_file


def load_channel_analytics(channel_dir: Path) -> dict[str, Any]:
    """Load channel-level analytics from channel_analytics.json.

    Args:
        channel_dir: Path to the channel directory.

    Returns:
        Dict with traffic sources, countries, etc., or empty dict.
    """
    analytics_file = Path(channel_dir) / "channel_analytics.json"
    if not analytics_file.exists():
        return {}
    return json.loads(analytics_file.read_text(encoding="utf-8"))


def save_channel_analytics(channel_dir: Path, data: dict[str, Any]) -> Path:
    """Save channel-level analytics to channel_analytics.json.

    Args:
        channel_dir: Path to the channel directory.
        data: Channel analytics dict.

    Returns:
        Path to the saved file.
    """
    channel_path = Path(channel_dir)
    channel_path.mkdir(parents=True, exist_ok=True)
    analytics_file = channel_path / "channel_analytics.json"
    analytics_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved channel analytics to %s", analytics_file)
    return analytics_file


def load_channel_info(channel_dir: Path) -> dict[str, Any]:
    """Load channel profile from channel_info.json.

    Args:
        channel_dir: Path to the channel directory.

    Returns:
        Dict with channel profile data, or empty dict.
    """
    info_file = Path(channel_dir) / "channel_info.json"
    if not info_file.exists():
        return {}
    return json.loads(info_file.read_text(encoding="utf-8"))


def save_channel_info(channel_dir: Path, data: dict[str, Any]) -> Path:
    """Save channel profile to channel_info.json.

    Args:
        channel_dir: Path to the channel directory.
        data: Channel profile dict.

    Returns:
        Path to the saved file.
    """
    channel_path = Path(channel_dir)
    channel_path.mkdir(parents=True, exist_ok=True)
    info_file = channel_path / "channel_info.json"
    info_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved channel info to %s", info_file)
    return info_file


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _apply_analytics_to_video(
    video: dict[str, Any],
    video_id: str,
    analytics_data: dict[str, dict[str, int | float]],
    refreshed_at: str,
) -> bool:
    """Apply analytics data to a single video dict.

    Args:
        video: Video dict to update in-place.
        video_id: YouTube video ID.
        analytics_data: Full analytics data dict.
        refreshed_at: ISO timestamp for last_refreshed.

    Returns:
        True if the video was updated.
    """
    if video_id not in analytics_data:
        return False

    metrics = analytics_data[video_id]
    for api_name, field_name in METRIC_TO_FIELD.items():
        if api_name in metrics:
            val = metrics[api_name]
            if "percentage" in field_name or "ctr" in field_name.lower():
                video[field_name] = round(float(val), 2)
            elif isinstance(val, float) and val == int(val):
                video[field_name] = int(val)
            else:
                video[field_name] = val

    video["last_refreshed"] = refreshed_at
    return True


def update_metadata_with_analytics(
    channel_dir: Path,
    analytics_data: dict[str, dict[str, int | float]],
    transcripts: dict[str, str] | None = None,
) -> int:
    """Update existing metadata.json with fresh analytics and optionally transcripts.

    Merges analytics into existing video entries. Does not add new videos.

    Args:
        channel_dir: Path to the channel directory.
        analytics_data: Dict mapping video_id -> {metric: value, ...}.
        transcripts: Optional dict mapping video_id -> transcript text.

    Returns:
        Number of videos updated.
    """
    metadata = load_metadata(channel_dir)
    if not metadata:
        return 0

    refreshed_at = datetime.now().isoformat()
    transcripts = transcripts or {}
    updated = 0

    for video in metadata:
        url = video.get("url", "")
        vid_id = _extract_video_id(url)
        if not vid_id:
            continue

        if _apply_analytics_to_video(video, vid_id, analytics_data, refreshed_at):
            updated += 1

        if vid_id in transcripts:
            video["transcript"] = transcripts[vid_id]

    save_metadata(channel_dir, metadata)
    return updated


def build_metadata_from_all_videos(
    api_videos: list[dict[str, Any]],
    analytics_data: dict[str, dict[str, int | float]],
    existing_metadata: list[dict[str, Any]],
    transcripts: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build full metadata list from API videos + analytics, merging with existing.

    Preserves tags and transcripts from existing metadata when available.

    Args:
        api_videos: Videos fetched from YouTube Data API.
        analytics_data: Per-video analytics data.
        existing_metadata: Current metadata.json contents.
        transcripts: Optional dict mapping video_id -> transcript text.

    Returns:
        Complete metadata list sorted by views descending.
    """
    refreshed_at = datetime.now().isoformat()
    transcripts = transcripts or {}

    # Index existing metadata by video ID for fast lookup
    existing_by_id: dict[str, dict[str, Any]] = {}
    for v in existing_metadata:
        vid = _extract_video_id(v.get("url", ""))
        if vid:
            existing_by_id[vid] = v

    result: list[dict[str, Any]] = []
    for api_v in api_videos:
        vid = api_v["video_id"]
        base = existing_by_id.get(vid, {})

        entry: dict[str, Any] = {
            "title": base.get("title") or api_v.get("title", ""),
            "description": base.get("description") or api_v.get("description", ""),
            "url": api_v.get("url", f"https://www.youtube.com/watch?v={vid}"),
            "published_at": api_v.get("published_at", base.get("published_at", "")),
        }

        # Preserve tags from existing
        if "tags" in base:
            entry["tags"] = base["tags"]

        # Transcript: prefer freshly fetched, else existing
        entry["transcript"] = transcripts.get(vid) or base.get("transcript", "")

        _apply_analytics_to_video(entry, vid, analytics_data, refreshed_at)
        entry["last_refreshed"] = refreshed_at
        result.append(entry)

    # Sort by views descending (most popular first)
    result.sort(key=lambda v: v.get("views", 0), reverse=True)
    return result
