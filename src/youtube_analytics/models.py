"""
Data models for YouTube channel analytics.

Provides dataclasses for per-video metrics, channel profiles,
channel-level analytics, and competitor video data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VideoMetrics:
    """Parsed metrics for a single video."""

    title: str
    url: str
    video_id: str = ""
    description: str = ""
    published_at: str = ""
    duration_seconds: int = 0
    thumbnail: str = ""
    category: str = ""
    is_short: bool = False
    tags: list[str] = field(default_factory=list)
    transcript: str = ""

    # Core metrics
    views: int = 0
    likes: int = 0
    dislikes: int = 0
    comments: int = 0
    shares: int = 0
    engaged_views: int = 0

    # Retention
    estimated_minutes_watched: float = 0
    average_view_duration_seconds: int = 0
    average_view_percentage: float = 0

    # Subscriber impact
    subscribers_gained: int = 0
    subscribers_lost: int = 0

    # Playlist activity
    videos_added_to_playlists: int = 0
    videos_removed_from_playlists: int = 0

    # Reach
    thumbnail_impressions: int = 0
    thumbnail_ctr_percentage: float = 0

    last_refreshed: str = ""

    @property
    def net_subscribers(self) -> int:
        return self.subscribers_gained - self.subscribers_lost

    @property
    def engagement_rate(self) -> float:
        """Engagement rate = (likes + comments + shares) / views * 100."""
        if self.views == 0:
            return 0.0
        return round((self.likes + self.comments + self.shares) / self.views * 100, 2)

    @property
    def subscriber_efficiency(self) -> float:
        """Subscribers gained per 1000 views."""
        if self.views == 0:
            return 0.0
        return round(self.subscribers_gained / self.views * 1000, 2)

    @property
    def share_rate(self) -> float:
        """Shares per 1000 views."""
        if self.views == 0:
            return 0.0
        return round(self.shares / self.views * 1000, 2)

    @classmethod
    def from_dict(cls, data: dict) -> VideoMetrics:
        """Create VideoMetrics from a metadata.json video entry."""
        url = data.get("url", "")
        video_id = data.get("video_id", "")
        if not video_id and url:
            video_id = _extract_video_id(url)

        return cls(
            title=data.get("title", ""),
            url=url,
            video_id=video_id,
            description=data.get("description", ""),
            published_at=data.get("published_at", ""),
            duration_seconds=data.get("duration_seconds", 0) or 0,
            thumbnail=data.get("thumbnail", ""),
            category=data.get("category", ""),
            is_short=data.get("is_short", False),
            tags=data.get("tags", []),
            transcript=data.get("transcript", ""),
            views=data.get("views", 0) or 0,
            likes=data.get("likes", 0) or 0,
            dislikes=data.get("dislikes", 0) or 0,
            comments=data.get("comments", 0) or 0,
            shares=data.get("shares", 0) or 0,
            engaged_views=data.get("engaged_views", 0) or 0,
            estimated_minutes_watched=data.get("estimated_minutes_watched", 0) or 0,
            average_view_duration_seconds=data.get("average_view_duration_seconds", 0) or 0,
            average_view_percentage=data.get("average_view_percentage", 0) or 0,
            subscribers_gained=data.get("subscribers_gained", 0) or 0,
            subscribers_lost=data.get("subscribers_lost", 0) or 0,
            videos_added_to_playlists=data.get("videos_added_to_playlists", 0) or 0,
            videos_removed_from_playlists=data.get("videos_removed_from_playlists", 0) or 0,
            thumbnail_impressions=data.get("thumbnail_impressions", 0) or 0,
            thumbnail_ctr_percentage=data.get("thumbnail_ctr_percentage", 0) or 0,
            last_refreshed=data.get("last_refreshed", ""),
        )


@dataclass
class ChannelProfile:
    """Channel-level metadata from YouTube Data API."""

    channel_id: str = ""
    title: str = ""
    description: str = ""
    custom_url: str = ""
    published_at: str = ""
    country: str = ""
    subscriber_count: int = 0
    hidden_subscriber_count: bool = False
    view_count: int = 0
    video_count: int = 0
    keywords: str = ""
    topic_categories: list[str] = field(default_factory=list)
    thumbnails: dict[str, str] = field(default_factory=dict)
    privacy_status: str = "public"
    is_linked: bool = False
    long_uploads_status: str = ""
    made_for_kids: bool = False
    self_declared_made_for_kids: bool = False
    unsubscribed_trailer: str = ""
    last_refreshed: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ChannelProfile:
        """Create ChannelProfile from a channel_info.json entry."""
        return cls(
            channel_id=data.get("channel_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            custom_url=data.get("custom_url", ""),
            published_at=data.get("published_at", ""),
            country=data.get("country", ""),
            subscriber_count=data.get("subscriber_count", 0) or 0,
            hidden_subscriber_count=data.get("hidden_subscriber_count", False),
            view_count=data.get("view_count", 0) or 0,
            video_count=data.get("video_count", 0) or 0,
            keywords=data.get("keywords", ""),
            topic_categories=data.get("topic_categories", []),
            thumbnails=data.get("thumbnails", {}),
            privacy_status=data.get("privacy_status", "public"),
            is_linked=data.get("is_linked", False),
            long_uploads_status=data.get("long_uploads_status", ""),
            made_for_kids=data.get("made_for_kids", False),
            self_declared_made_for_kids=data.get("self_declared_made_for_kids", False),
            unsubscribed_trailer=data.get("unsubscribed_trailer", ""),
            last_refreshed=data.get("last_refreshed", ""),
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "channel_id": self.channel_id,
            "title": self.title,
            "description": self.description,
            "custom_url": self.custom_url,
            "published_at": self.published_at,
            "country": self.country,
            "subscriber_count": self.subscriber_count,
            "hidden_subscriber_count": self.hidden_subscriber_count,
            "view_count": self.view_count,
            "video_count": self.video_count,
            "keywords": self.keywords,
            "topic_categories": self.topic_categories,
            "thumbnails": self.thumbnails,
            "privacy_status": self.privacy_status,
            "is_linked": self.is_linked,
            "long_uploads_status": self.long_uploads_status,
            "made_for_kids": self.made_for_kids,
            "self_declared_made_for_kids": self.self_declared_made_for_kids,
            "unsubscribed_trailer": self.unsubscribed_trailer,
            "last_refreshed": self.last_refreshed,
        }


@dataclass
class ChannelAnalytics:
    """Channel-level analytics: traffic, geography, devices, demographics."""

    traffic_sources: list[dict] = field(default_factory=list)
    top_countries: list[dict] = field(default_factory=list)
    subscribed_breakdown: list[dict] = field(default_factory=list)
    device_types: list[dict] = field(default_factory=list)
    operating_systems: list[dict] = field(default_factory=list)
    demographics: list[dict] = field(default_factory=list)
    sharing_services: list[dict] = field(default_factory=list)
    daily_trends: list[dict] = field(default_factory=list)
    channel_metadata: dict[str, int] = field(default_factory=dict)
    last_refreshed: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ChannelAnalytics:
        """Create ChannelAnalytics from a channel_analytics.json entry."""
        return cls(
            traffic_sources=data.get("traffic_sources", []),
            top_countries=data.get("top_countries", []),
            subscribed_breakdown=data.get("subscribed_breakdown", []),
            device_types=data.get("device_types", []),
            operating_systems=data.get("operating_systems", []),
            demographics=data.get("demographics", []),
            sharing_services=data.get("sharing_services", []),
            daily_trends=data.get("daily_trends", []),
            channel_metadata=data.get("channel_metadata", {}),
            last_refreshed=data.get("last_refreshed", ""),
        )


@dataclass
class ChannelSummary:
    """Aggregated channel-level statistics computed from video data."""

    channel_name: str = ""
    total_videos: int = 0
    total_shorts: int = 0
    total_long_form: int = 0
    total_views: int = 0
    total_engaged_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_subscribers_gained: int = 0
    total_subscribers_lost: int = 0
    total_minutes_watched: float = 0
    avg_retention_percentage: float = 0
    avg_engagement_rate: float = 0
    avg_subscriber_efficiency: float = 0
    last_refreshed: str = ""

    @property
    def net_subscribers(self) -> int:
        return self.total_subscribers_gained - self.total_subscribers_lost

    @property
    def watch_time_hours(self) -> float:
        return round(self.total_minutes_watched / 60, 1)


@dataclass
class CompetitorVideo:
    """Public video data from a competitor channel (API-key access only)."""

    video_id: str = ""
    title: str = ""
    url: str = ""
    published_at: str = ""
    duration_seconds: int = 0
    is_short: bool = False
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def engagement_rate(self) -> float:
        """Engagement rate = (likes + comments) / views * 100."""
        if self.view_count == 0:
            return 0.0
        return round((self.like_count + self.comment_count) / self.view_count * 100, 2)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "duration_seconds": self.duration_seconds,
            "is_short": self.is_short,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "description": self.description,
            "tags": self.tags,
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
