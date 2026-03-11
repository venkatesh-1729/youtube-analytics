"""
Data models for YouTube channel analytics.

Provides dataclasses for per-video metrics, channel profiles,
channel-level analytics, and competitor video data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC

from youtube_analytics.utils import extract_video_id, parse_publish_date


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

    # yt-dlp enrichment fields
    hashtags: list[str] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)
    language: str = ""
    aspect_ratio: str = ""
    resolution: str = ""
    has_captions: bool = False
    caption_languages: list[str] = field(default_factory=list)
    topic_categories: list[str] = field(default_factory=list)
    age_restricted: bool = False

    # Additional Analytics API metrics
    unique_viewers: int = 0
    card_impressions: int = 0
    card_click_rate: float = 0
    end_screen_clicks: int = 0
    end_screen_click_rate: float = 0

    # Data API fields (from videos.list)
    default_language: str = ""
    default_audio_language: str = ""
    definition: str = ""
    licensed_content: bool = False

    last_refreshed: str = ""

    # --- Computed properties ---

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

    @property
    def duration_bracket(self) -> str:
        """Categorize video by duration.

        Returns one of: micro, short, medium, standard, long, extended.
        """
        s = self.duration_seconds
        if s <= 30:
            return "micro"
        if s <= 60:
            return "short"
        if s <= 300:
            return "medium"
        if s <= 900:
            return "standard"
        if s <= 1800:
            return "long"
        return "extended"

    @property
    def publish_day_of_week(self) -> str:
        """Day of week the video was published (e.g. 'Monday')."""
        dt = parse_publish_date(self.published_at)
        if dt is None:
            return ""
        return dt.strftime("%A")

    @property
    def days_since_published(self) -> int:
        """Number of days since the video was published."""
        from datetime import datetime

        dt = parse_publish_date(self.published_at)
        if dt is None:
            return 0
        delta = datetime.now(tz=UTC) - dt
        return max(0, delta.days)

    @property
    def views_per_day(self) -> float:
        """Average views per day since publish."""
        days = self.days_since_published
        if days == 0:
            return float(self.views)
        return round(self.views / days, 1)

    # --- Serialization ---

    @classmethod
    def from_dict(cls, data: dict) -> VideoMetrics:
        """Create VideoMetrics from a metadata.json video entry."""
        url = data.get("url", "")
        video_id = data.get("video_id", "")
        if not video_id and url:
            video_id = extract_video_id(url)

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
            hashtags=data.get("hashtags", []),
            chapters=data.get("chapters", []),
            language=data.get("language", ""),
            aspect_ratio=data.get("aspect_ratio", ""),
            resolution=data.get("resolution", ""),
            has_captions=data.get("has_captions", False),
            caption_languages=data.get("caption_languages", []),
            topic_categories=data.get("topic_categories", []),
            age_restricted=data.get("age_restricted", False),
            unique_viewers=data.get("unique_viewers", 0) or 0,
            card_impressions=data.get("card_impressions", 0) or 0,
            card_click_rate=data.get("card_click_rate", 0) or 0,
            end_screen_clicks=data.get("end_screen_clicks", 0) or 0,
            end_screen_click_rate=data.get("end_screen_click_rate", 0) or 0,
            default_language=data.get("default_language", ""),
            default_audio_language=data.get("default_audio_language", ""),
            definition=data.get("definition", ""),
            licensed_content=data.get("licensed_content", False),
            last_refreshed=data.get("last_refreshed", ""),
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "title": self.title,
            "url": self.url,
            "video_id": self.video_id,
            "description": self.description,
            "published_at": self.published_at,
            "duration_seconds": self.duration_seconds,
            "thumbnail": self.thumbnail,
            "category": self.category,
            "is_short": self.is_short,
            "tags": self.tags,
            "transcript": self.transcript,
            "views": self.views,
            "likes": self.likes,
            "dislikes": self.dislikes,
            "comments": self.comments,
            "shares": self.shares,
            "engaged_views": self.engaged_views,
            "estimated_minutes_watched": self.estimated_minutes_watched,
            "average_view_duration_seconds": self.average_view_duration_seconds,
            "average_view_percentage": self.average_view_percentage,
            "subscribers_gained": self.subscribers_gained,
            "subscribers_lost": self.subscribers_lost,
            "videos_added_to_playlists": self.videos_added_to_playlists,
            "videos_removed_from_playlists": self.videos_removed_from_playlists,
            "thumbnail_impressions": self.thumbnail_impressions,
            "thumbnail_ctr_percentage": self.thumbnail_ctr_percentage,
            "hashtags": self.hashtags,
            "chapters": self.chapters,
            "language": self.language,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "has_captions": self.has_captions,
            "caption_languages": self.caption_languages,
            "topic_categories": self.topic_categories,
            "age_restricted": self.age_restricted,
            "unique_viewers": self.unique_viewers,
            "card_impressions": self.card_impressions,
            "card_click_rate": self.card_click_rate,
            "end_screen_clicks": self.end_screen_clicks,
            "end_screen_click_rate": self.end_screen_click_rate,
            "default_language": self.default_language,
            "default_audio_language": self.default_audio_language,
            "definition": self.definition,
            "licensed_content": self.licensed_content,
            "last_refreshed": self.last_refreshed,
        }


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
