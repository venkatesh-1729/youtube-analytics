"""
Analytics computation: summaries, rankings, insights, and competitor comparison.

Based on Inkwell's backend/core/analytics.py, enhanced with competitor analysis.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from youtube_analytics.models import (
    ChannelAnalytics,
    ChannelSummary,
    CompetitorVideo,
    VideoMetrics,
)

logger = logging.getLogger(__name__)


def compute_summary(
    channel_name: str,
    videos: list[VideoMetrics],
) -> ChannelSummary:
    """Compute aggregate channel statistics from video data.

    Args:
        channel_name: Name/identifier for the channel.
        videos: List of video metrics.

    Returns:
        ChannelSummary with totals and averages.
    """
    if not videos:
        return ChannelSummary(channel_name=channel_name)

    total_views = sum(v.views for v in videos)
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    # Weighted average retention (by views)
    weighted_retention = 0.0
    if total_views > 0:
        weighted_retention = sum(
            v.average_view_percentage * v.views for v in videos
        ) / total_views

    engagement_rates = [v.engagement_rate for v in videos if v.views > 0]
    sub_efficiencies = [v.subscriber_efficiency for v in videos if v.views > 0]

    refreshed = max((v.last_refreshed for v in videos if v.last_refreshed), default="")

    return ChannelSummary(
        channel_name=channel_name,
        total_videos=len(videos),
        total_shorts=len(shorts),
        total_long_form=len(long_form),
        total_views=total_views,
        total_engaged_views=sum(v.engaged_views for v in videos),
        total_likes=sum(v.likes for v in videos),
        total_comments=sum(v.comments for v in videos),
        total_shares=sum(v.shares for v in videos),
        total_subscribers_gained=sum(v.subscribers_gained for v in videos),
        total_subscribers_lost=sum(v.subscribers_lost for v in videos),
        total_minutes_watched=sum(v.estimated_minutes_watched for v in videos),
        avg_retention_percentage=round(weighted_retention, 2),
        avg_engagement_rate=round(
            sum(engagement_rates) / len(engagement_rates), 2
        ) if engagement_rates else 0,
        avg_subscriber_efficiency=round(
            sum(sub_efficiencies) / len(sub_efficiencies), 2
        ) if sub_efficiencies else 0,
        last_refreshed=refreshed,
    )


def rank_videos(
    videos: list[VideoMetrics],
    sort_by: str = "views",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Rank videos by a given metric.

    Args:
        videos: List of video metrics.
        sort_by: Metric to sort by (views, retention, subscribers, shares, engagement, watch_time).
        limit: Max results to return.

    Returns:
        List of video dicts with metrics and computed scores.
    """
    sort_key_map = {
        "views": lambda v: v.views,
        "retention": lambda v: v.average_view_percentage,
        "subscribers": lambda v: v.subscriber_efficiency,
        "shares": lambda v: v.share_rate,
        "engagement": lambda v: v.engagement_rate,
        "watch_time": lambda v: v.estimated_minutes_watched,
    }

    key_fn = sort_key_map.get(sort_by, sort_key_map["views"])
    ranked = sorted(videos, key=key_fn, reverse=True)[:limit]

    return [
        {
            "rank": i + 1,
            "title": v.title,
            "url": v.url,
            "views": v.views,
            "likes": v.likes,
            "comments": v.comments,
            "shares": v.shares,
            "engagement_rate": v.engagement_rate,
            "retention": v.average_view_percentage,
            "subscriber_efficiency": v.subscriber_efficiency,
            "share_rate": v.share_rate,
            "net_subscribers": v.net_subscribers,
            "is_short": v.is_short,
            "watch_time_minutes": v.estimated_minutes_watched,
        }
        for i, v in enumerate(ranked)
    ]


def compute_insights(
    videos: list[VideoMetrics],
    channel_analytics: ChannelAnalytics | None = None,
) -> list[dict[str, Any]]:
    """Generate actionable insights from channel data.

    Analyzes video performance, traffic sources, and audience demographics
    to produce data-driven recommendations.

    Args:
        videos: List of video metrics.
        channel_analytics: Optional channel-level analytics.

    Returns:
        List of insight dicts with type, title, description, and data.
    """
    if not videos:
        return []

    insights: list[dict[str, Any]] = []

    # --- 1. Top performers ---
    by_views = sorted(videos, key=lambda v: v.views, reverse=True)
    insights.append({
        "type": "top_performers",
        "title": "🏆 Top Performing Videos",
        "description": "Videos with the highest view counts",
        "data": [
            {"title": v.title, "views": v.views, "engagement": v.engagement_rate}
            for v in by_views[:5]
        ],
    })

    # --- 2. Best retention ---
    with_views = [v for v in videos if v.views >= 100]
    by_retention = sorted(with_views, key=lambda v: v.average_view_percentage, reverse=True)
    if by_retention:
        insights.append({
            "type": "best_retention",
            "title": "👀 Highest Retention Videos",
            "description": "Videos that keep viewers watching the longest (avg view %)",
            "data": [
                {"title": v.title, "retention": v.average_view_percentage, "views": v.views}
                for v in by_retention[:5]
            ],
        })

    # --- 3. Subscriber magnets ---
    by_sub_eff = sorted(with_views, key=lambda v: v.subscriber_efficiency, reverse=True)
    if by_sub_eff:
        insights.append({
            "type": "subscriber_magnets",
            "title": "🧲 Best Subscriber Converters",
            "description": "Videos that gain the most subscribers per 1000 views",
            "data": [
                {
                    "title": v.title,
                    "subscriber_efficiency": v.subscriber_efficiency,
                    "net_subs": v.net_subscribers,
                    "views": v.views,
                }
                for v in by_sub_eff[:5]
            ],
        })

    # --- 4. Most shared ---
    by_shares = sorted(with_views, key=lambda v: v.share_rate, reverse=True)
    if by_shares:
        insights.append({
            "type": "most_shared",
            "title": "📤 Most Shareable Content",
            "description": "Videos with the highest share rate per 1000 views",
            "data": [
                {"title": v.title, "share_rate": v.share_rate, "shares": v.shares}
                for v in by_shares[:5]
            ],
        })

    # --- 5. Underperformers ---
    median_views = sorted(v.views for v in with_views)[len(with_views) // 2] if with_views else 0
    underperformers = [v for v in with_views if v.views < median_views * 0.3]
    if underperformers:
        insights.append({
            "type": "underperformers",
            "title": "⚠️ Underperforming Videos",
            "description": f"Videos with views significantly below median ({median_views:,})",
            "data": [
                {"title": v.title, "views": v.views, "retention": v.average_view_percentage}
                for v in sorted(underperformers, key=lambda v: v.views)[:5]
            ],
        })

    # --- 6. Content type analysis ---
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]
    if shorts and long_form:
        avg_short_views = sum(v.views for v in shorts) / len(shorts)
        avg_long_views = sum(v.views for v in long_form) / len(long_form)
        avg_short_retention = sum(v.average_view_percentage for v in shorts) / len(shorts)
        avg_long_retention = sum(v.average_view_percentage for v in long_form) / len(long_form)

        insights.append({
            "type": "content_format",
            "title": "📊 Shorts vs Long-Form Performance",
            "description": "Comparison between short and long-form content",
            "data": {
                "shorts": {
                    "count": len(shorts),
                    "avg_views": round(avg_short_views),
                    "avg_retention": round(avg_short_retention, 1),
                },
                "long_form": {
                    "count": len(long_form),
                    "avg_views": round(avg_long_views),
                    "avg_retention": round(avg_long_retention, 1),
                },
            },
        })

    # --- 7. Tag analysis ---
    all_tags: list[str] = []
    for v in videos:
        all_tags.extend(tag.lower() for tag in v.tags)

    if all_tags:
        tag_counts = Counter(all_tags).most_common(15)
        insights.append({
            "type": "popular_tags",
            "title": "🏷️ Most Used Tags",
            "description": "Tags you use most frequently",
            "data": [{"tag": tag, "count": count} for tag, count in tag_counts],
        })

    # --- 8. Traffic source analysis ---
    if channel_analytics and channel_analytics.traffic_sources:
        sorted_sources = sorted(
            channel_analytics.traffic_sources,
            key=lambda s: s.get("views", 0),
            reverse=True,
        )
        total_traffic_views = sum(s.get("views", 0) for s in sorted_sources)

        insights.append({
            "type": "traffic_sources",
            "title": "🌐 Traffic Sources",
            "description": "Where your viewers are coming from",
            "data": [
                {
                    "source": s.get("insightTrafficSourceType", ""),
                    "views": s.get("views", 0),
                    "percentage": round(
                        s.get("views", 0) / total_traffic_views * 100, 1
                    ) if total_traffic_views > 0 else 0,
                }
                for s in sorted_sources[:10]
            ],
        })

    # --- 9. Geographic analysis ---
    if channel_analytics and channel_analytics.top_countries:
        insights.append({
            "type": "geography",
            "title": "🌍 Audience Geography",
            "description": "Top countries by views",
            "data": channel_analytics.top_countries[:10],
        })

    # --- 10. Sharing analysis ---
    if channel_analytics and channel_analytics.sharing_services:
        insights.append({
            "type": "sharing_services",
            "title": "📱 Sharing Platforms",
            "description": "Where viewers share your content",
            "data": channel_analytics.sharing_services[:10],
        })

    return insights


def compare_with_competitors(
    own_videos: list[VideoMetrics],
    competitor_videos: dict[str, list[CompetitorVideo]],
) -> dict[str, Any]:
    """Compare own channel performance against competitors.

    Args:
        own_videos: Own channel's video metrics.
        competitor_videos: Dict mapping competitor name -> their video list.

    Returns:
        Competitive analysis dict with benchmarks and gaps.
    """
    own_shorts = [v for v in own_videos if v.is_short]
    own_long = [v for v in own_videos if not v.is_short]

    analysis: dict[str, Any] = {
        "own_channel": {
            "total_videos": len(own_videos),
            "shorts": len(own_shorts),
            "long_form": len(own_long),
            "avg_views": round(
                sum(v.views for v in own_videos) / len(own_videos)
            ) if own_videos else 0,
            "avg_engagement_rate": round(
                sum(v.engagement_rate for v in own_videos) / len(own_videos), 2
            ) if own_videos else 0,
        },
        "competitors": {},
    }

    for comp_name, comp_vids in competitor_videos.items():
        if not comp_vids:
            continue

        comp_shorts = [v for v in comp_vids if v.is_short]
        comp_long = [v for v in comp_vids if not v.is_short]

        analysis["competitors"][comp_name] = {
            "total_videos": len(comp_vids),
            "shorts": len(comp_shorts),
            "long_form": len(comp_long),
            "avg_views": round(
                sum(v.view_count for v in comp_vids) / len(comp_vids)
            ),
            "avg_engagement_rate": round(
                sum(v.engagement_rate for v in comp_vids) / len(comp_vids), 2
            ),
            "top_videos": [
                {"title": v.title, "views": v.view_count, "engagement": v.engagement_rate}
                for v in sorted(comp_vids, key=lambda x: x.view_count, reverse=True)[:5]
            ],
        }

    # Determine content gaps: competitor tags not used by own channel
    own_tags = set()
    for v in own_videos:
        own_tags.update(tag.lower() for tag in v.tags)

    for comp_name, comp_vids in competitor_videos.items():
        comp_tags: set[str] = set()
        for v in comp_vids:
            comp_tags.update(tag.lower() for tag in v.tags)

        if comp_name in analysis["competitors"]:
            gap_tags = comp_tags - own_tags
            analysis["competitors"][comp_name]["unique_tags"] = sorted(gap_tags)[:20]

    return analysis
