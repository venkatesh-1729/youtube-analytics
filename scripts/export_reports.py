#!/usr/bin/env python3
"""Generate comprehensive markdown reports from channel data.

Usage:
    python scripts/export_reports.py <channel_dir>

Generates:
    - longform_analysis.md  (long-form videos — every field)
    - all_videos_stats.md   (every video — summary table + full detail)
"""

import json
import sys
from pathlib import Path


def load_data(channel_dir: Path):
    return json.loads((channel_dir / "metadata.json").read_text())


def fmt_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def esc(text: str) -> str:
    """Escape pipe characters for markdown tables."""
    return str(text).replace("|", "\\|")


def engagement_rate(v: dict) -> float:
    views = v.get("views", 0) or 1
    interactions = (
        v.get("likes", 0) + v.get("comments", 0) + v.get("shares", 0)
    )
    return interactions / views * 100


def render_video_full(v: dict, idx: int) -> list[str]:
    """Render a single video with ALL available fields."""
    lines = []
    title = v.get("title", "Untitled")
    lines.append(f"### {idx}. {title}")
    lines.append("")

    # Core identifiers + publish info
    pub_raw = v.get("published_at", "")
    pub_date = pub_raw[:10] if pub_raw else "N/A"
    pub_time = pub_raw[11:16] if len(pub_raw) > 11 else "N/A"
    # Day of week
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(pub_raw.replace("Z", "+00:00"))
        pub_day = dt.strftime("%A")  # Monday, Tuesday, etc.
        days_since = (
            _dt.now(dt.tzinfo) - dt
        ).days
    except Exception:
        pub_day = "N/A"
        days_since = 0

    dur_s = v.get("duration_seconds", 0)
    avg_dur = v.get("average_view_duration_seconds", 0)
    completion_pct = (avg_dur / dur_s * 100) if dur_s else 0
    views = v.get("views", 0)
    views_per_day = views / max(days_since, 1)

    lines.append("#### Identifiers & Timing")
    lines.append(f"- **URL:** {v.get('url', 'N/A')}")
    lines.append(f"- **Video ID:** {v.get('video_id', 'N/A')}")
    lines.append(f"- **Published:** {pub_date} ({pub_day}) at {pub_time} UTC")
    lines.append(f"- **Days since publish:** {days_since}")
    lines.append(
        f"- **Type:** "
        f"{'Short' if v.get('is_short') else 'Long-form'}"
    )
    lines.append(f"- **Duration:** {fmt_duration(dur_s)} ({dur_s}s)")
    lines.append("")

    # Description
    desc = v.get("description", "")
    if desc:
        lines.append("#### Description")
        lines.append("```")
        lines.append(desc.strip())
        lines.append("```")
        lines.append("")

    # Performance metrics
    lines.append("#### Performance Metrics")
    lines.append(f"- **Views:** {v.get('views', 0):,}")
    lines.append(f"- **Likes:** {v.get('likes', 0):,}")
    lines.append(f"- **Dislikes:** {v.get('dislikes', 0):,}")
    lines.append(f"- **Comments:** {v.get('comments', 0):,}")
    lines.append(f"- **Shares:** {v.get('shares', 0):,}")
    lines.append(f"- **Engaged views:** {v.get('engaged_views', 0):,}")
    eng = engagement_rate(v)
    lines.append(f"- **Engagement rate:** {eng:.2f}%")
    lines.append("")

    # Watch time & retention
    lines.append("#### Watch Time & Retention")
    wt_min = v.get("estimated_minutes_watched", 0)
    lines.append(f"- **Watch time:** {wt_min:,} min ({wt_min / 60:,.1f} hrs)")
    lines.append(
        f"- **Avg view duration:** "
        f"{fmt_duration(avg_dur)} ({avg_dur}s)"
    )
    lines.append(
        f"- **Avg view percentage:** "
        f"{v.get('average_view_percentage', 0):.1f}%"
    )
    lines.append(f"- **Completion rate:** {completion_pct:.1f}%")
    lines.append(f"- **Views per day:** {views_per_day:,.0f}")
    lines.append("")

    # Subscribers
    lines.append("#### Subscriber Impact")
    gained = v.get("subscribers_gained", 0)
    lost = v.get("subscribers_lost", 0)
    sub_rate = (gained / max(views, 1)) * 100
    lines.append(f"- **Subscribers gained:** +{gained:,}")
    lines.append(f"- **Subscribers lost:** -{lost:,}")
    lines.append(f"- **Net:** +{gained - lost:,}")
    lines.append(f"- **Sub conversion rate:** {sub_rate:.3f}%")
    lines.append(
        f"- **Playlist adds:** "
        f"{v.get('videos_added_to_playlists', 0):,}"
    )
    lines.append(
        f"- **Playlist removes:** "
        f"{v.get('videos_removed_from_playlists', 0):,}"
    )
    lines.append("")

    # Reach
    ti = v.get("thumbnail_impressions", 0)
    ctr = v.get("thumbnail_ctr_percentage", 0)
    if ti or ctr:
        lines.append("#### Reach (Impressions)")
        lines.append(f"- **Thumbnail impressions:** {ti:,}")
        lines.append(f"- **Thumbnail CTR:** {ctr:.2f}%")
        lines.append("")

    # Engagement features
    ci = v.get("card_impressions", 0)
    ccr = v.get("card_click_rate", 0)
    es_clicks = v.get("end_screen_clicks", 0)
    escr = v.get("end_screen_click_rate", 0)
    if ci or es_clicks:
        lines.append("#### Cards & End Screens")
        lines.append(f"- **Card impressions:** {ci:,}")
        lines.append(f"- **Card click rate:** {ccr:.2f}%")
        lines.append(f"- **End screen clicks:** {es_clicks:,}")
        lines.append(f"- **End screen click rate:** {escr:.2f}%")
        lines.append("")

    # Content metadata
    lines.append("#### Content Metadata")
    lines.append(f"- **Category:** {v.get('category', 'N/A')}")
    lines.append(f"- **Language:** {v.get('default_language', 'N/A')}")
    lines.append(
        f"- **Audio language:** "
        f"{v.get('default_audio_language', 'N/A')}"
    )
    lines.append(f"- **Resolution:** {v.get('resolution', 'N/A')}")
    lines.append(f"- **Aspect ratio:** {v.get('aspect_ratio', 'N/A')}")
    lines.append(f"- **Definition:** {v.get('definition', 'N/A')}")
    lines.append(f"- **Captions:** {v.get('caption', 'N/A')}")
    lines.append(
        f"- **Licensed content:** {v.get('licensed_content', 'N/A')}"
    )
    lines.append("")

    # Tags & hashtags
    tags = v.get("tags", [])
    hashtags = v.get("hashtags", [])
    topics = v.get("topic_categories", [])
    lines.append("#### Tags & Topics")
    lines.append(f"- **Tags ({len(tags)}):** {', '.join(tags) if tags else 'None'}")
    lines.append(
        f"- **Hashtags ({len(hashtags)}):** "
        f"{', '.join(hashtags) if hashtags else 'None'}"
    )
    lines.append(
        f"- **Topic categories:** "
        f"{', '.join(topics) if topics else 'None'}"
    )
    lines.append("")

    # Chapters
    chapters = v.get("chapters", [])
    if chapters:
        lines.append(f"#### Chapters ({len(chapters)})")
        for ch in chapters:
            start = fmt_duration(int(ch.get("start_time", 0)))
            lines.append(f"- [{start}] {ch.get('title', '')}")
        lines.append("")

    # Transcript
    transcript = v.get("transcript", "")
    if transcript:
        lines.append("#### Transcript")
        lines.append("```")
        lines.append(transcript.strip())
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("")
    return lines


def generate_longform_report(meta: list[dict]) -> str:
    longform = [v for v in meta if not v.get("is_short", False)]
    longform.sort(key=lambda v: v.get("views", 0), reverse=True)

    lines = []
    lines.append("# Long-Form Video Analysis")
    lines.append(f"\nTotal long-form videos: {len(longform)}\n")

    # Summary
    total_views = sum(v.get("views", 0) for v in longform)
    total_wt = sum(v.get("estimated_minutes_watched", 0) for v in longform)
    total_subs = sum(v.get("subscribers_gained", 0) for v in longform)
    avg_ret = (
        sum(v.get("average_view_percentage", 0) for v in longform)
        / max(len(longform), 1)
    )

    lines.append("## Summary")
    lines.append(f"- **Total views:** {total_views:,}")
    lines.append(f"- **Total watch time:** {total_wt / 60:,.1f} hours")
    lines.append(f"- **Subscribers gained:** {total_subs:,}")
    lines.append(f"- **Avg retention:** {avg_ret:.1f}%\n")

    # Quick comparison table
    lines.append("## Quick Comparison\n")
    lines.append(
        "| # | Title | Views | Likes | Shares | Watch Time (hrs) "
        "| Avg View % | Subs | Engagement % |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, v in enumerate(longform, 1):
        title = esc(v.get("title", "")[:55])
        lines.append(
            f"| {i} | {title} "
            f"| {v.get('views', 0):,} "
            f"| {v.get('likes', 0):,} "
            f"| {v.get('shares', 0):,} "
            f"| {v.get('estimated_minutes_watched', 0) / 60:,.1f} "
            f"| {v.get('average_view_percentage', 0):.1f}% "
            f"| +{v.get('subscribers_gained', 0):,} "
            f"| {engagement_rate(v):.2f}% |"
        )

    lines.append("")

    # Full detail per video
    lines.append("## Detailed Video Profiles\n")
    for i, v in enumerate(longform, 1):
        lines.extend(render_video_full(v, i))

    return "\n".join(lines)


def generate_all_videos_report(meta: list[dict]) -> str:
    shorts = [v for v in meta if v.get("is_short")]
    longform = [v for v in meta if not v.get("is_short", False)]

    lines = []
    lines.append("# All Video Statistics")
    lines.append(
        f"\nTotal: {len(meta)} videos "
        f"({len(shorts)} Shorts, {len(longform)} Long-form)\n"
    )

    # Summary table
    lines.append("## Overview Table (sorted by views)\n")
    lines.append(
        "| # | Type | Title | Views | Likes | Shares "
        "| Watch Time (hrs) | Avg View % | Net Subs | Engagement % |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")

    for i, v in enumerate(meta, 1):
        vtype = "Short" if v.get("is_short") else "Long"
        title = esc(v.get("title", "")[:50])
        subs_net = (
            v.get("subscribers_gained", 0) - v.get("subscribers_lost", 0)
        )
        lines.append(
            f"| {i} | {vtype} | {title} "
            f"| {v.get('views', 0):,} "
            f"| {v.get('likes', 0):,} "
            f"| {v.get('shares', 0):,} "
            f"| {v.get('estimated_minutes_watched', 0) / 60:,.1f} "
            f"| {v.get('average_view_percentage', 0):.1f}% "
            f"| +{subs_net:,} "
            f"| {engagement_rate(v):.2f}% |"
        )

    lines.append("")

    # Full detail per video
    lines.append("## Detailed Video Profiles\n")
    for i, v in enumerate(meta, 1):
        lines.extend(render_video_full(v, i))

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_reports.py <channel_dir>")
        sys.exit(1)

    channel_dir = Path(sys.argv[1])
    meta = load_data(channel_dir)

    lf = generate_longform_report(meta)
    out1 = channel_dir / "longform_analysis.md"
    out1.write_text(lf)
    print(f"✅ {out1.name} ({len(lf.splitlines())} lines)")

    av = generate_all_videos_report(meta)
    out2 = channel_dir / "all_videos_stats.md"
    out2.write_text(av)
    print(f"✅ {out2.name} ({len(av.splitlines())} lines)")


if __name__ == "__main__":
    main()
