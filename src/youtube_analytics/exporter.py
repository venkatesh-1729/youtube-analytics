"""
LLM-ready export for AI-driven content strategy.

Generates structured markdown or JSON snapshots suitable for
feeding into LLMs to get content recommendations and insights.
Includes format-separated (Shorts vs Long-form) analysis.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from youtube_analytics.analyzer import (
    compare_with_competitors,
    compute_format_summary,
    compute_insights,
    compute_summary,
)
from youtube_analytics.models import (
    ChannelAnalytics,
    ChannelProfile,
    ChannelSummary,
    CompetitorVideo,
    VideoMetrics,
)
from youtube_analytics.storage import load_channel_analytics, load_channel_info, load_metadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_channel_snapshot(
    channel_dir: Path,
    *,
    fmt: str = "markdown",
    top_n: int = 10,
) -> str:
    """Export a comprehensive channel snapshot for LLM analysis.

    Args:
        channel_dir: Path to channel data directory.
        fmt: Output format — "markdown" or "json".
        top_n: Number of top/bottom videos to include.

    Returns:
        Formatted string (markdown or JSON) ready for LLM consumption.
    """
    channel_path = Path(channel_dir)

    # Load all data
    raw_metadata = load_metadata(channel_path)
    raw_analytics = load_channel_analytics(channel_path)
    raw_info = load_channel_info(channel_path)

    videos = [VideoMetrics.from_dict(v) for v in raw_metadata]
    channel_analytics = ChannelAnalytics.from_dict(raw_analytics) if raw_analytics else None
    profile = ChannelProfile.from_dict(raw_info) if raw_info else None

    channel_name = profile.title if profile else channel_path.name
    summary = compute_summary(channel_name, videos)
    insights = compute_insights(videos, channel_analytics)

    if fmt == "json":
        return _export_json(profile, summary, videos, insights, channel_analytics, top_n)

    return _export_markdown(profile, summary, videos, insights, channel_analytics, top_n)


def export_for_ideation(
    channel_dir: Path,
    competitor_dirs: list[Path] | None = None,
) -> str:
    """Export a focused document for content ideation and strategy.

    Produces a prompt-ready document with format-separated analysis,
    highlighting what works, what doesn't, and competitor gaps.

    Args:
        channel_dir: Path to own channel data directory.
        competitor_dirs: Optional paths to competitor data directories.

    Returns:
        Markdown document suitable for LLM prompting.
    """
    channel_path = Path(channel_dir)
    raw_metadata = load_metadata(channel_path)
    raw_analytics = load_channel_analytics(channel_path)
    raw_info = load_channel_info(channel_path)

    videos = [VideoMetrics.from_dict(v) for v in raw_metadata]
    channel_analytics = ChannelAnalytics.from_dict(raw_analytics) if raw_analytics else None
    profile = ChannelProfile.from_dict(raw_info) if raw_info else None
    channel_name = profile.title if profile else channel_path.name

    lines: list[str] = []
    lines.append(f"# Content Strategy Brief: {channel_name}")
    lines.append("")
    lines.append("Use this data to recommend content ideas, identify improvement areas,")
    lines.append("and provide specific, actionable strategy suggestions.")
    lines.append("")

    # --- Format summary ---
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    lines.append("## 📊 Content Format Breakdown")
    lines.append("")
    if shorts:
        avg_s_views = sum(v.views for v in shorts) / len(shorts)
        avg_s_ret = sum(v.average_view_percentage for v in shorts) / len(shorts)
        avg_s_eng = sum(v.engagement_rate for v in shorts if v.views > 0)
        n_s = len([v for v in shorts if v.views > 0])
        lines.append(
            f"- **Shorts:** {len(shorts)} videos, "
            f"avg {avg_s_views:,.0f} views, "
            f"avg {avg_s_ret:.1f}% retention, "
            f"avg {avg_s_eng/n_s if n_s else 0:.2f}% engagement"
        )
    if long_form:
        avg_l_views = sum(v.views for v in long_form) / len(long_form)
        avg_l_ret = sum(v.average_view_percentage for v in long_form) / len(long_form)
        avg_l_eng = sum(v.engagement_rate for v in long_form if v.views > 0)
        n_l = len([v for v in long_form if v.views > 0])
        lines.append(
            f"- **Long-form:** {len(long_form)} videos, "
            f"avg {avg_l_views:,.0f} views, "
            f"avg {avg_l_ret:.1f}% retention, "
            f"avg {avg_l_eng/n_l if n_l else 0:.2f}% engagement"
        )
    lines.append("")

    # --- What's working — by format ---
    lines.append("## ✅ What's Working Well")
    lines.append("")

    for label, subset in [("Shorts", shorts), ("Long-form", long_form)]:
        if not subset:
            continue

        top_by_views = sorted(subset, key=lambda v: v.views, reverse=True)[:3]
        lines.append(f"### Top {label} (by views)")
        for v in top_by_views:
            lines.append(
                f"- **{v.title}** — {v.views:,} views, "
                f"{v.engagement_rate}% engagement, "
                f"{v.share_rate} shares/1K views"
            )
        lines.append("")

        top_retention = sorted(
            [v for v in subset if v.views >= 100],
            key=lambda v: v.average_view_percentage,
            reverse=True,
        )[:3]
        if top_retention:
            lines.append(f"### Best {label} Retention")
            for v in top_retention:
                lines.append(
                    f"- **{v.title}** — {v.average_view_percentage}% retained, "
                    f"{v.views:,} views"
                )
            lines.append("")

    # Subscriber magnets (all formats)
    high_subs = sorted(videos, key=lambda v: v.subscriber_efficiency, reverse=True)[:5]
    if high_subs:
        lines.append("### Best for Subscriber Growth")
        for v in high_subs:
            fmt_label = "Short" if v.is_short else "Long"
            lines.append(
                f"- [{fmt_label}] **{v.title}** — {v.subscriber_efficiency} subs/1K views, "
                f"+{v.net_subscribers} net"
            )
        lines.append("")

    # --- What's not working ---
    lines.append("## ⚠️ Areas for Improvement")
    lines.append("")

    for label, subset in [("Shorts", shorts), ("Long-form", long_form)]:
        if not subset:
            continue
        low_retention = sorted(
            [v for v in subset if v.views >= 100],
            key=lambda v: v.average_view_percentage,
        )[:3]
        if low_retention:
            lines.append(f"### Lowest {label} Retention")
            for v in low_retention:
                lines.append(
                    f"- **{v.title}** — {v.average_view_percentage}% retained, "
                    f"{v.views:,} views"
                )
            lines.append("")

    # Subscriber loss
    sub_loss = sorted(videos, key=lambda v: v.subscribers_lost, reverse=True)[:3]
    sub_loss_notable = [v for v in sub_loss if v.subscribers_lost > 0]
    if sub_loss_notable:
        lines.append("### Highest Subscriber Loss")
        for v in sub_loss_notable:
            fmt_label = "Short" if v.is_short else "Long"
            lines.append(
                f"- [{fmt_label}] **{v.title}** — lost {v.subscribers_lost} subscribers "
                f"(gained {v.subscribers_gained})"
            )
        lines.append("")

    # --- Publishing patterns ---
    day_views: dict[str, list[int]] = {}
    for v in videos:
        day = v.publish_day_of_week
        if day:
            day_views.setdefault(day, []).append(v.views)
    if day_views:
        lines.append("## 📅 Publishing Patterns")
        lines.append("")
        day_stats = sorted(
            [
                (day, round(sum(views) / len(views)), len(views))
                for day, views in day_views.items()
            ],
            key=lambda d: d[1],
            reverse=True,
        )
        for day, avg, count in day_stats:
            lines.append(f"- **{day}:** avg {avg:,} views ({count} videos)")
        lines.append("")

    # Tag/topic analysis
    all_tags: list[str] = []
    for v in videos:
        all_tags.extend(tag.lower() for tag in v.tags)
    if all_tags:
        lines.append("### Top Content Topics (by tag frequency)")
        for tag, count in Counter(all_tags).most_common(10):
            lines.append(f"- {tag} ({count})")
        lines.append("")

    # --- Traffic insights ---
    if channel_analytics and channel_analytics.traffic_sources:
        lines.append("## 🌐 Traffic Source Insights")
        lines.append("")
        total = sum(s.get("views", 0) for s in channel_analytics.traffic_sources)
        for src in sorted(
            channel_analytics.traffic_sources,
            key=lambda s: s.get("views", 0),
            reverse=True,
        )[:5]:
            pct = round(src.get("views", 0) / total * 100, 1) if total > 0 else 0
            lines.append(
                f"- **{src.get('insightTrafficSourceType', 'Unknown')}:** "
                f"{src.get('views', 0):,} views ({pct}%)"
            )
        lines.append("")

    # --- Competitor comparison ---
    if competitor_dirs:
        _append_competitor_section(lines, videos, competitor_dirs)

    # --- Call to action ---
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Questions to Answer")
    lines.append("")
    lines.append("Based on the data above, please provide:")
    lines.append("1. **3 content ideas** that align with what's working well")
    lines.append("2. **2 specific improvements** for underperforming content areas")
    lines.append("3. **1 new content series** idea based on competitor gaps or emerging trends")
    lines.append("4. **Optimal posting schedule** based on daily trends and traffic patterns")
    lines.append("5. **Format recommendation** — should focus shift more to Shorts or Long-form?")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _append_competitor_section(
    lines: list[str],
    videos: list[VideoMetrics],
    competitor_dirs: list[Path],
) -> None:
    """Append competitor comparison section to the lines list."""
    competitor_data: dict[str, list[CompetitorVideo]] = {}
    for comp_dir in competitor_dirs:
        comp_path = Path(comp_dir)
        comp_metadata = load_metadata(comp_path)
        comp_name = comp_path.name
        competitor_data[comp_name] = [
            CompetitorVideo(
                video_id=v.get("video_id", ""),
                title=v.get("title", ""),
                url=v.get("url", ""),
                view_count=v.get("view_count", v.get("views", 0)),
                like_count=v.get("like_count", v.get("likes", 0)),
                comment_count=v.get("comment_count", v.get("comments", 0)),
                duration_seconds=v.get("duration_seconds", 0),
                is_short=v.get("is_short", False),
                published_at=v.get("published_at", ""),
                tags=v.get("tags", []),
            )
            for v in comp_metadata
        ]

    comparison = compare_with_competitors(videos, competitor_data)

    lines.append("## 🔍 Competitor Comparison")
    lines.append("")
    for comp_name, comp_data in comparison.get("competitors", {}).items():
        lines.append(f"### {comp_name}")
        lines.append(f"- Videos: {comp_data['total_videos']}")
        lines.append(f"- Avg views: {comp_data['avg_views']:,}")
        lines.append(f"- Avg engagement: {comp_data['avg_engagement_rate']}%")
        lines.append("")

        if comp_data.get("top_videos"):
            lines.append("Top performing videos:")
            for tv in comp_data["top_videos"][:3]:
                lines.append(f"  - {tv['title']} ({tv['views']:,} views)")
            lines.append("")

        unique_tags = comp_data.get("unique_tags", [])
        if unique_tags:
            lines.append(f"Topics they cover that you don't: {', '.join(unique_tags[:10])}")
            lines.append("")


def _export_markdown(
    profile: ChannelProfile | None,
    summary: ChannelSummary,
    videos: list[VideoMetrics],
    insights: list[dict[str, Any]],
    channel_analytics: ChannelAnalytics | None,
    top_n: int,
) -> str:
    """Build markdown snapshot with format-separated sections."""
    lines: list[str] = []

    # Header
    name = profile.title if profile else summary.channel_name
    lines.append(f"# Channel Snapshot: {name}")
    lines.append(f"*Last refreshed: {summary.last_refreshed}*")
    lines.append("")

    # Profile
    if profile:
        lines.append("## Channel Profile")
        lines.append(f"- **Subscribers:** {profile.subscriber_count:,}")
        lines.append(f"- **Total views:** {profile.view_count:,}")
        lines.append(f"- **Videos:** {profile.video_count}")
        lines.append(f"- **Country:** {profile.country}")
        if profile.keywords:
            lines.append(f"- **Keywords:** {profile.keywords[:200]}")
        lines.append("")

    # Summary
    lines.append("## Performance Summary")
    lines.append(f"- **Total videos analyzed:** {summary.total_videos}")
    lines.append(f"  - Shorts: {summary.total_shorts} | Long-form: {summary.total_long_form}")
    lines.append(f"- **Total views:** {summary.total_views:,}")
    lines.append(f"- **Watch time:** {summary.watch_time_hours:,.1f} hours")
    lines.append(f"- **Net subscribers:** +{summary.net_subscribers:,}")
    lines.append(f"- **Total shares:** {summary.total_shares:,}")
    lines.append(f"- **Avg retention:** {summary.avg_retention_percentage}%")
    lines.append(f"- **Avg engagement rate:** {summary.avg_engagement_rate}%")
    lines.append("")

    # Format breakdown
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    if shorts and long_form:
        format_summary = compute_format_summary(videos)
        lines.append("## Shorts vs Long-Form Breakdown")
        lines.append("")
        lines.append("| Metric | Shorts | Long-Form |")
        lines.append("|--------|--------|-----------|")
        s = format_summary["shorts"]
        lf = format_summary["long_form"]
        lines.append(f"| Count | {s['count']} | {lf['count']} |")
        lines.append(f"| Avg Views | {s['avg_views']:,} | {lf['avg_views']:,} |")
        lines.append(f"| Avg Retention | {s['avg_retention']}% | {lf['avg_retention']}% |")
        lines.append(f"| Avg Engagement | {s['avg_engagement']}% | {lf['avg_engagement']}% |")
        wt_s = s['total_watch_time_hours']
        wt_lf = lf['total_watch_time_hours']
        lines.append(f"| Watch Time (hrs) | {wt_s} | {wt_lf} |")
        sg_s = s['total_subscribers_gained']
        sg_lf = lf['total_subscribers_gained']
        lines.append(f"| Subs Gained | {sg_s:,} | {sg_lf:,} |")
        lines.append("")

    # Top videos — by format
    for label, subset in [("Shorts", shorts), ("Long-Form", long_form)]:
        if not subset:
            continue
        by_views = sorted(subset, key=lambda v: v.views, reverse=True)
        n = min(top_n, len(by_views))
        lines.append(f"## Top {n} {label} by Views")
        lines.append("")
        lines.append("| # | Title | Views | Retention | Engagement | Subs ± |")
        lines.append("|---|-------|-------|-----------|------------|--------|")
        for i, v in enumerate(by_views[:n]):
            lines.append(
                f"| {i + 1} | {v.title[:50]} | {v.views:,} | "
                f"{v.average_view_percentage}% | {v.engagement_rate}% | "
                f"+{v.subscribers_gained}/-{v.subscribers_lost} |"
            )
        lines.append("")

    # Bottom videos
    by_views_all = sorted(videos, key=lambda v: v.views, reverse=True)
    lines.append(f"## Bottom {min(top_n, 5)} Videos by Views")
    lines.append("")
    bottom = by_views_all[-min(top_n, 5):]
    for v in bottom:
        fmt_label = "Short" if v.is_short else "Long"
        lines.append(
            f"- [{fmt_label}] **{v.title[:60]}** — {v.views:,} views, "
            f"{v.average_view_percentage}% retention"
        )
    lines.append("")

    # Insights
    for insight in insights:
        lines.append(f"## {insight['title']}")
        lines.append(f"*{insight['description']}*")
        lines.append("")

        data = insight.get("data", [])
        if isinstance(data, list):
            for item in data[:5]:
                if isinstance(item, dict):
                    parts = [f"{k}: {v}" for k, v in item.items()]
                    lines.append(f"- {' | '.join(parts)}")
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    details = ", ".join(f"{dk}: {dv}" for dk, dv in v.items())
                    lines.append(f"- **{k}:** {details}")
                else:
                    lines.append(f"- **{k}:** {v}")
        lines.append("")

    return "\n".join(lines)


def _export_json(
    profile: ChannelProfile | None,
    summary: ChannelSummary,
    videos: list[VideoMetrics],
    insights: list[dict[str, Any]],
    channel_analytics: ChannelAnalytics | None,
    top_n: int,
) -> str:
    """Build JSON snapshot with format separation."""
    shorts = [v for v in videos if v.is_short]
    long_form = [v for v in videos if not v.is_short]

    by_views = sorted(videos, key=lambda v: v.views, reverse=True)
    shorts_by_views = sorted(shorts, key=lambda v: v.views, reverse=True)
    long_by_views = sorted(long_form, key=lambda v: v.views, reverse=True)

    def _video_summary(v: VideoMetrics) -> dict:
        return {
            "title": v.title,
            "url": v.url,
            "views": v.views,
            "retention": v.average_view_percentage,
            "engagement_rate": v.engagement_rate,
            "shares": v.shares,
            "net_subscribers": v.net_subscribers,
            "is_short": v.is_short,
            "duration_bracket": v.duration_bracket,
            "publish_day": v.publish_day_of_week,
            "views_per_day": v.views_per_day,
        }

    format_summary = compute_format_summary(videos) if shorts and long_form else {}

    data = {
        "channel_profile": profile.to_dict() if profile else {},
        "summary": {
            "total_videos": summary.total_videos,
            "total_shorts": summary.total_shorts,
            "total_long_form": summary.total_long_form,
            "total_views": summary.total_views,
            "watch_time_hours": summary.watch_time_hours,
            "net_subscribers": summary.net_subscribers,
            "total_shares": summary.total_shares,
            "avg_retention": summary.avg_retention_percentage,
            "avg_engagement_rate": summary.avg_engagement_rate,
        },
        "format_comparison": format_summary,
        "top_shorts": [_video_summary(v) for v in shorts_by_views[:top_n]],
        "top_long_form": [_video_summary(v) for v in long_by_views[:top_n]],
        "top_videos": [_video_summary(v) for v in by_views[:top_n]],
        "bottom_videos": [
            {
                "title": v.title,
                "url": v.url,
                "views": v.views,
                "retention": v.average_view_percentage,
                "is_short": v.is_short,
            }
            for v in by_views[-min(top_n, 5):]
        ],
        "insights": insights,
    }

    return json.dumps(data, indent=2, ensure_ascii=False)
