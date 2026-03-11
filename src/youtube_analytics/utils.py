"""
Shared utility helpers for youtube_analytics.

Single source of truth for video ID extraction, ISO duration parsing,
and other reusable helpers.
"""

from __future__ import annotations

import re
from datetime import datetime


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from a URL.

    Supports standard watch URLs, short URLs, and Shorts URLs.

    Args:
        url: YouTube video URL.

    Returns:
        11-character video ID, or empty string if extraction fails.
    """
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def parse_iso_duration(duration: str) -> int:
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


def parse_publish_date(published_at: str) -> datetime | None:
    """Parse a YouTube publishedAt timestamp to a datetime.

    Args:
        published_at: ISO timestamp string (e.g. "2026-02-08T12:29:43Z").

    Returns:
        datetime object, or None if parsing fails.
    """
    if not published_at:
        return None
    try:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
