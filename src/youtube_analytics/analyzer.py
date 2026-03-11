"""
Analytics computation: summaries, rankings, insights, and competitor comparison.

Provides both combined and format-specific (Shorts vs Long-form) analysis.
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


# ---------------------------------------------------------------------------
# Channel summary
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Video ranking
# ---------------------------------------------------------------------------

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
            "duration_bracket": v.duration_bracket,
        }
        for i, v in enumerate(ranked)
    ]


# ---------------------------------------------------------------------------
# Format-specific analysis (Shorts vs Long-form)
# ---------------------------------------------------------------------------

def _format_stats(videos: list[VideoMetrics]) -> dict[str, Any]:
    """Compute aggregate stats for a list of videos (helper).

    Args:
        videos: Subset of videos (e.g. only Shorts or only Long-form).

    Returns:
        Dict with count, averages, totals, and top performer.
    """
    if not videos:
        return {"count": 0}

    total_views = sum(v.views for v in videos)
    with_views = [v for v in videos if v.views > 0]
    top = max(videos, key=lambda v: v.views)

    return {
        "count": len(videos),
        "total_views": total_views,
        "avg_views": round(total_views / len(videos)),
        "avg_retention": round(
            sum(v.average_view_percentage for v in videos) / len(videos), 1
        ),
        "avg_engagement": round(
            sum(v.engagement_rate for v in with_views) / len(with_views), 2
        ) if with_views else 0,
        "total_watch_time_hours": round(
            sum(v.estimated_minutes_watched for v in videos) / 60, 1
        ),
        "total_subscribers_gained": sum(v.subscribers_gained for v in videos),
        "avg_subscriber_efficiency": round(
            sum(v.subscriber_efficiency for v in with_views) / len(with_views), 2
        ) if with_views else 0,
        "avg_share_rate": round(
            sum(v.share_rate for v in with_views) / len(with_views), 2
        ) if with_views else 0,
        "top_performer": {
            "title": top.title,
            "views": top.views,
            "retention": top.average_view_percentage,
        },
    }


def compute_format_summary(videos: list[VideoMetrics]) -> dict[str, Any]:
    """Compute separate stats for Shorts vs Long-form.

    Args:
        videos: All videos for the channel.

    Returns:
        Dict with 'shorts', 'long_form', and 'comparison' sections.
    """
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    shorts_stats = _format_stats(shorts)
    long_stats = _format_stats(long_form)

    comparison: dict[str, Any] = {}
    if shorts_stats["count"] > 0 and long_stats["count"] > 0:
        comparison = {
            "views_ratio": round(
                shorts_stats["avg_views"] / long_stats["avg_views"], 2
            ) if long_stats["avg_views"] > 0 else 0,
            "retention_diff": round(
                shorts_stats["avg_retention"] - long_stats["avg_retention"], 1
            ),
            "subs_per_view_winner": (
                "shorts" if shorts_stats["avg_subscriber_efficiency"]
                > long_stats["avg_subscriber_efficiency"] else "long_form"
            ),
            "share_rate_winner": (
                "shorts" if shorts_stats["avg_share_rate"]
                > long_stats["avg_share_rate"] else "long_form"
            ),
        }

    return {
        "shorts": shorts_stats,
        "long_form": long_stats,
        "comparison": comparison,
    }


def compute_shorts_insights(shorts: list[VideoMetrics]) -> list[dict[str, Any]]:
    """Generate Shorts-specific insights.

    Analyzes replay rates, optimal duration, and topic performance
    for short-form content.

    Args:
        shorts: List of Shorts-only VideoMetrics.

    Returns:
        List of insight dicts.
    """
    if not shorts:
        return []

    insights: list[dict[str, Any]] = []

    # --- Replay rate analysis (avg_view_percentage > 100% means replays) ---
    replayed = [v for v in shorts if v.average_view_percentage > 100]
    if replayed:
        insights.append({
            "type": "shorts_replay",
            "title": "🔄 High Replay Shorts",
            "description": (
                f"{len(replayed)}/{len(shorts)} Shorts have replay rates (>100% avg view). "
                "These hook viewers into watching again."
            ),
            "data": [
                {
                    "title": v.title,
                    "replay_rate": f"{v.average_view_percentage}%",
                    "views": v.views,
                }
                for v in sorted(replayed, key=lambda v: v.average_view_percentage, reverse=True)[:5]
            ],
        })

    # --- Optimal duration bucket ---
    duration_buckets: dict[str, list[VideoMetrics]] = {
        "0-15s": [],
        "15-30s": [],
        "30-45s": [],
        "45-60s": [],
    }
    for v in shorts:
        s = v.duration_seconds
        if s <= 15:
            duration_buckets["0-15s"].append(v)
        elif s <= 30:
            duration_buckets["15-30s"].append(v)
        elif s <= 45:
            duration_buckets["30-45s"].append(v)
        else:
            duration_buckets["45-60s"].append(v)

    bucket_stats = []
    for bucket_name, bucket_videos in duration_buckets.items():
        if bucket_videos:
            avg_views = sum(v.views for v in bucket_videos) / len(bucket_videos)
            avg_ret = sum(v.average_view_percentage for v in bucket_videos) / len(bucket_videos)
            bucket_stats.append({
                "duration": bucket_name,
                "count": len(bucket_videos),
                "avg_views": round(avg_views),
                "avg_retention": round(avg_ret, 1),
            })

    if bucket_stats:
        best_bucket = max(bucket_stats, key=lambda b: b["avg_views"])
        insights.append({
            "type": "shorts_duration",
            "title": "⏱️ Optimal Short Duration",
            "description": f"Best performing duration: {best_bucket['duration']} "
                          f"(avg {best_bucket['avg_views']:,} views)",
            "data": bucket_stats,
        })

    # --- Top Shorts tags ---
    all_tags: list[str] = []
    for v in shorts:
        all_tags.extend(tag.lower() for tag in v.tags)
    if all_tags:
        tag_counts = Counter(all_tags).most_common(10)
        insights.append({
            "type": "shorts_tags",
            "title": "🏷️ Top Shorts Tags",
            "description": "Most used tags across Shorts content",
            "data": [{"tag": t, "count": c} for t, c in tag_counts],
        })

    return insights


def compute_longform_insights(long_form: list[VideoMetrics]) -> list[dict[str, Any]]:
    """Generate Long-form specific insights.

    Analyzes retention patterns, watch time contributions,
    and optimal video lengths.

    Args:
        long_form: List of Long-form-only VideoMetrics.

    Returns:
        List of insight dicts.
    """
    if not long_form:
        return []

    insights: list[dict[str, Any]] = []

    # --- Watch time contribution ---
    total_wt = sum(v.estimated_minutes_watched for v in long_form)
    if total_wt > 0:
        top_wt = sorted(long_form, key=lambda v: v.estimated_minutes_watched, reverse=True)[:5]
        insights.append({
            "type": "longform_watch_time",
            "title": "⏰ Watch Time Champions",
            "description": "Long-form videos driving the most watch time",
            "data": [
                {
                    "title": v.title,
                    "watch_time_hours": round(v.estimated_minutes_watched / 60, 1),
                    "pct_of_total": round(v.estimated_minutes_watched / total_wt * 100, 1),
                    "views": v.views,
                }
                for v in top_wt
            ],
        })

    # --- Optimal length analysis ---
    length_buckets: dict[str, list[VideoMetrics]] = {
        "1-5 min": [],
        "5-10 min": [],
        "10-20 min": [],
        "20+ min": [],
    }
    for v in long_form:
        m = v.duration_seconds / 60
        if m <= 5:
            length_buckets["1-5 min"].append(v)
        elif m <= 10:
            length_buckets["5-10 min"].append(v)
        elif m <= 20:
            length_buckets["10-20 min"].append(v)
        else:
            length_buckets["20+ min"].append(v)

    bucket_stats = []
    for name, vids in length_buckets.items():
        if vids:
            avg_views = sum(v.views for v in vids) / len(vids)
            avg_ret = sum(v.average_view_percentage for v in vids) / len(vids)
            avg_sub = sum(v.subscriber_efficiency for v in vids if v.views > 0)
            n_with_views = len([v for v in vids if v.views > 0])
            bucket_stats.append({
                "length": name,
                "count": len(vids),
                "avg_views": round(avg_views),
                "avg_retention": round(avg_ret, 1),
                "avg_sub_efficiency": round(avg_sub / n_with_views, 2) if n_with_views else 0,
            })

    if bucket_stats:
        best = max(bucket_stats, key=lambda b: b["avg_views"])
        insights.append({
            "type": "longform_optimal_length",
            "title": "📏 Optimal Video Length",
            "description": f"Best performing length: {best['length']} "
                          f"(avg {best['avg_views']:,} views)",
            "data": bucket_stats,
        })

    # --- Chapter analysis ---
    with_chapters = [v for v in long_form if v.chapters]
    without_chapters = [v for v in long_form if not v.chapters]
    if with_chapters and without_chapters:
        avg_views_with = sum(v.views for v in with_chapters) / len(with_chapters)
        avg_views_without = sum(v.views for v in without_chapters) / len(without_chapters)
        avg_ret_with = sum(v.average_view_percentage for v in with_chapters) / len(with_chapters)
        avg_ret_without = (
            sum(v.average_view_percentage for v in without_chapters)
            / len(without_chapters)
        )

        insights.append({
            "type": "longform_chapters",
            "title": "📑 Chapter Impact",
            "description": "How chapters affect video performance",
            "data": {
                "with_chapters": {
                    "count": len(with_chapters),
                    "avg_views": round(avg_views_with),
                    "avg_retention": round(avg_ret_with, 1),
                },
                "without_chapters": {
                    "count": len(without_chapters),
                    "avg_views": round(avg_views_without),
                    "avg_retention": round(avg_ret_without, 1),
                },
            },
        })

    return insights


# ---------------------------------------------------------------------------
# Combined insights
# ---------------------------------------------------------------------------

def compute_insights(
    videos: list[VideoMetrics],
    channel_analytics: ChannelAnalytics | None = None,
) -> list[dict[str, Any]]:
    """Generate actionable insights from channel data.

    Analyzes video performance, traffic sources, and audience demographics
    to produce data-driven recommendations. Includes format-specific insights.

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

    # --- 6. Format-specific insights ---
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    # Combined format comparison
    if shorts and long_form:
        format_summary = compute_format_summary(videos)
        insights.append({
            "type": "content_format",
            "title": "📊 Shorts vs Long-Form Performance",
            "description": "Comparison between short and long-form content",
            "data": {
                "shorts": format_summary["shorts"],
                "long_form": format_summary["long_form"],
                "comparison": format_summary.get("comparison", {}),
            },
        })

    # Shorts-specific
    shorts_insights = compute_shorts_insights(shorts)
    insights.extend(shorts_insights)

    # Long-form-specific
    longform_insights = compute_longform_insights(long_form)
    insights.extend(longform_insights)

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

    # --- 8. Publishing day analysis ---
    day_views: dict[str, list[int]] = {}
    for v in videos:
        day = v.publish_day_of_week
        if day:
            day_views.setdefault(day, []).append(v.views)

    if day_views:
        day_stats = [
            {
                "day": day,
                "count": len(views),
                "avg_views": round(sum(views) / len(views)),
            }
            for day, views in day_views.items()
        ]
        day_stats.sort(key=lambda d: d["avg_views"], reverse=True)
        best_day = day_stats[0]
        insights.append({
            "type": "publish_day",
            "title": "📅 Best Publishing Days",
            "description": f"Best day: {best_day['day']} (avg {best_day['avg_views']:,} views)",
            "data": day_stats,
        })

    # --- 9. Traffic source analysis ---
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

    # --- 10. Geographic analysis ---
    if channel_analytics and channel_analytics.top_countries:
        insights.append({
            "type": "geography",
            "title": "🌍 Audience Geography",
            "description": "Top countries by views",
            "data": channel_analytics.top_countries[:10],
        })

    # --- 11. Sharing analysis ---
    if channel_analytics and channel_analytics.sharing_services:
        insights.append({
            "type": "sharing_services",
            "title": "📱 Sharing Platforms",
            "description": "Where viewers share your content",
            "data": channel_analytics.sharing_services[:10],
        })

    return insights


# ---------------------------------------------------------------------------
# Competitor comparison
# ---------------------------------------------------------------------------

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
