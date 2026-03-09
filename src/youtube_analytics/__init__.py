"""
YouTube Analytics — Shared module for channel data collection and analysis.

Consolidates YouTube metadata/analytics gathering from content-engine and Inkwell
into a single, reusable package.

Usage:
    from youtube_analytics import sync_own_channel, fetch_competitor, export_for_llm
"""

from youtube_analytics.analyzer import compute_insights, compute_summary, rank_videos
from youtube_analytics.exporter import export_channel_snapshot, export_for_ideation
from youtube_analytics.fetcher import (
    fetch_all_channel_videos,
    fetch_analytics_per_video,
    fetch_channel_level_analytics,
    fetch_competitor_videos,
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

__all__ = [
    # Models
    "VideoMetrics",
    "ChannelProfile",
    "ChannelAnalytics",
    "ChannelSummary",
    "CompetitorVideo",
    # Fetcher
    "fetch_all_channel_videos",
    "fetch_analytics_per_video",
    "fetch_channel_level_analytics",
    "fetch_competitor_videos",
    # Storage
    "load_metadata",
    "save_metadata",
    "load_channel_analytics",
    "save_channel_analytics",
    "load_channel_info",
    "save_channel_info",
    # Analyzer
    "compute_summary",
    "compute_insights",
    "rank_videos",
    # Exporter
    "export_channel_snapshot",
    "export_for_ideation",
]
