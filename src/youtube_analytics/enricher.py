"""
yt-dlp based metadata enrichment for YouTube videos.

Extracts additional metadata not available through the YouTube API,
such as chapters, hashtags, resolution, aspect ratio, captions, etc.

Requires yt-dlp to be installed (optional dependency):
    pip install youtube-analytics[enrichment]
    # or: pip install yt-dlp
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

from youtube_analytics.utils import extract_video_id

logger = logging.getLogger(__name__)

# Fields we extract from yt-dlp JSON output
_YTDLP_FIELDS = [
    "chapters",
    "tags",
    "language",
    "width",
    "height",
    "resolution",
    "subtitles",
    "automatic_captions",
    "age_limit",
    "channel_follower_count",
    "categories",
    "like_count",
    "view_count",
    "comment_count",
    "duration",
    "original_url",
]


def _is_ytdlp_available() -> bool:
    """Check if yt-dlp is installed and accessible."""
    return shutil.which("yt-dlp") is not None


def _extract_hashtags(description: str) -> list[str]:
    """Extract #hashtags from video description.

    Args:
        description: Video description text.

    Returns:
        List of hashtags (without the # prefix), lowercased.
    """
    import re

    hashtags = re.findall(r"#(\w+)", description or "")
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for tag in hashtags:
        lower = tag.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result


def _compute_aspect_ratio(width: int, height: int) -> str:
    """Compute aspect ratio string from width and height.

    Args:
        width: Video width in pixels.
        height: Video height in pixels.

    Returns:
        Aspect ratio string like "16:9", "9:16", "1:1", or "other".
    """
    if not width or not height:
        return ""

    ratio = width / height
    if abs(ratio - 16 / 9) < 0.1:
        return "16:9"
    if abs(ratio - 9 / 16) < 0.1:
        return "9:16"
    if abs(ratio - 4 / 3) < 0.1:
        return "4:3"
    if abs(ratio - 1.0) < 0.1:
        return "1:1"
    return f"{width}:{height}"


def _resolution_label(height: int) -> str:
    """Convert pixel height to resolution label.

    Args:
        height: Video height in pixels.

    Returns:
        Resolution label like "1080p", "4K", etc.
    """
    if not height:
        return ""
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "1440p"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return f"{height}p"


def enrich_video(video_id: str) -> dict[str, Any]:
    """Fetch enrichment metadata for a single video using yt-dlp.

    Runs `yt-dlp --dump-json` and extracts additional fields not
    available through the YouTube API.

    Args:
        video_id: YouTube video ID.

    Returns:
        Dict with enrichment fields. Empty dict if yt-dlp fails.
    """
    if not _is_ytdlp_available():
        logger.warning("yt-dlp not installed; skipping enrichment for %s", video_id)
        return {}

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", "--no-warnings", url],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.debug("yt-dlp failed for %s: %s", video_id, result.stderr.strip())
            return {}

        data = json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        logger.warning("yt-dlp timed out for %s", video_id)
        return {}
    except json.JSONDecodeError as e:
        logger.warning("yt-dlp returned invalid JSON for %s: %s", video_id, e)
        return {}
    except Exception as e:
        logger.warning("Unexpected error enriching %s: %s", video_id, e)
        return {}

    # Parse enrichment fields
    width = data.get("width", 0) or 0
    height = data.get("height", 0) or 0

    # Extract caption languages from subtitles dict
    subtitles = data.get("subtitles", {}) or {}
    auto_captions = data.get("automatic_captions", {}) or {}
    caption_langs = sorted(set(list(subtitles.keys()) + list(auto_captions.keys())))

    # Parse chapters
    raw_chapters = data.get("chapters") or []
    chapters = [
        {
            "title": ch.get("title", ""),
            "start_time": ch.get("start_time", 0),
            "end_time": ch.get("end_time", 0),
        }
        for ch in raw_chapters
        if ch.get("title")
    ]

    # Extract hashtags from description
    description = data.get("description", "")
    hashtags = _extract_hashtags(description)

    enrichment: dict[str, Any] = {
        "hashtags": hashtags,
        "chapters": chapters,
        "language": data.get("language", ""),
        "aspect_ratio": _compute_aspect_ratio(width, height),
        "resolution": _resolution_label(height),
        "has_captions": bool(subtitles),
        "caption_languages": caption_langs,
        "topic_categories": data.get("categories", []),
        "age_restricted": (data.get("age_limit", 0) or 0) > 0,
    }

    # Also capture duration_seconds if not already set
    if data.get("duration"):
        enrichment["duration_seconds"] = int(data["duration"])

    # Determine is_short from duration
    dur = enrichment.get("duration_seconds", 0)
    if dur and dur <= 60:
        enrichment["is_short"] = True

    return enrichment


def enrich_videos(
    video_ids: list[str],
    existing: list[dict[str, Any]],
    *,
    skip_enriched: bool = True,
    delay_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    """Batch-enrich videos with yt-dlp metadata.

    Merges enrichment data into existing metadata dicts.

    Args:
        video_ids: List of video IDs to enrich.
        existing: Current metadata entries (modified in-place).
        skip_enriched: If True, skip videos that already have enrichment data.
        delay_seconds: Seconds to wait between yt-dlp calls (default: 1.0).

    Returns:
        The modified existing list.
    """
    import time

    if not _is_ytdlp_available():
        logger.warning(
            "yt-dlp not installed. Install with: pip install yt-dlp\n"
            "  or: pip install youtube-analytics[enrichment]"
        )
        return existing

    # Build lookup: video_id -> list index
    id_to_idx: dict[str, int] = {}
    for i, entry in enumerate(existing):
        vid = entry.get("video_id") or extract_video_id(entry.get("url", ""))
        if vid:
            id_to_idx[vid] = i

    enriched_count = 0
    skipped_count = 0

    for j, vid in enumerate(video_ids):
        idx = id_to_idx.get(vid)
        if idx is None:
            logger.debug("Video %s not found in metadata, skipping", vid)
            continue

        entry = existing[idx]

        # Skip if already enriched
        if skip_enriched and entry.get("resolution"):
            skipped_count += 1
            continue

        logger.info("Enriching %s: %s", vid, entry.get("title", "")[:60])
        data = enrich_video(vid)

        if data:
            # Merge enrichment into existing entry (don't overwrite existing values)
            for key, value in data.items():
                if key not in entry or not entry[key]:
                    entry[key] = value
            enriched_count += 1

        # Delay between calls to avoid rate limiting
        if j < len(video_ids) - 1:
            time.sleep(delay_seconds)

    logger.info(
        "Enrichment complete: %d enriched, %d skipped, %d total",
        enriched_count, skipped_count, len(video_ids),
    )
    return existing
