"""
YouTube Analytics — Shared module for channel data collection and analysis.

Consolidates YouTube metadata/analytics gathering from content-engine and Inkwell
into a single, reusable package.

Usage:
    from youtube_analytics import sync_own_channel, fetch_competitor, export_for_llm
"""

from youtube_analytics.analyzer import compute_insights, compute_summary, rank_videos
from youtube_analytics.exporter import export_channel_snapshot, export_for_ideation
from youtube_analytics.fetcher_competitor import (
    fetch_competitor_channel_info,
    fetch_competitor_videos,
)
from youtube_analytics.fetcher_own import (
    fetch_all_channel_videos,
    fetch_analytics_per_video,
    fetch_channel_level_analytics,
    fetch_video_details,
)
from youtube_analytics.models import (
    ChannelAnalytics,
    ChannelProfile,
    ChannelSummary,
    CompetitorVideo,
    VideoMetrics,
)
from youtube_analytics.storage import (
    load_channel_analytics,
    load_channel_info,
    load_metadata,
    save_channel_analytics,
    save_channel_info,
    save_metadata,
)
from youtube_analytics.utils import extract_video_id

__all__ = [
    "ChannelAnalytics",
    "ChannelProfile",
    "ChannelSummary",
    "CompetitorVideo",
    # Models
    "VideoMetrics",
    "compute_insights",
    # Analyzer
    "compute_summary",
    # Exporter
    "export_channel_snapshot",
    "export_for_ideation",
    # Utils
    "extract_video_id",
    # Fetcher — own channel
    "fetch_all_channel_videos",
    "fetch_analytics_per_video",
    "fetch_channel_level_analytics",
    # Fetcher — competitors
    "fetch_competitor_channel_info",
    "fetch_competitor_videos",
    "fetch_video_details",
    "load_channel_analytics",
    "load_channel_info",
    # Storage
    "load_metadata",
    "rank_videos",
    "save_channel_analytics",
    "save_channel_info",
    "save_metadata",
]
