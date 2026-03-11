"""
Transcript fetching for YouTube videos.

Uses youtube-transcript-api to fetch captions/subtitles.
No authentication required — works with public video IDs.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Delay between transcript fetches to avoid rate limiting
TRANSCRIPT_FETCH_DELAY = 1.0


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
