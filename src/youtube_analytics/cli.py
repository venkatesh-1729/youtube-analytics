"""
CLI for YouTube Analytics module.

Provides commands: sync, competitor, export, compare, insights.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync own channel: fetch videos, analytics, and channel info."""
    from youtube_analytics.auth import get_authenticated_services
    from youtube_analytics.fetcher import (
        fetch_all_channel_videos,
        fetch_analytics_per_video,
        fetch_channel_level_analytics,
        fetch_transcripts_for_videos,
        get_channel_info,
    )
    from youtube_analytics.storage import (
        build_metadata_from_all_videos,
        load_metadata,
        save_channel_analytics,
        save_channel_info,
        save_metadata,
        update_metadata_with_analytics,
    )

    channel_dir = Path(args.channel_dir)
    secrets_dir = Path(args.secrets_dir)

    print(f"🔐 Authenticating with YouTube APIs...")
    analytics_service, youtube_service = get_authenticated_services(secrets_dir)

    # Get channel info
    print(f"📡 Fetching channel info...")
    title, start_date, uploads_playlist, channel_metadata = get_channel_info(youtube_service)
    channel_metadata["last_refreshed"] = datetime.now().isoformat()
    save_channel_info(channel_dir, channel_metadata)
    print(f"✅ Channel: {title} (since {start_date})")

    if args.analytics_only:
        # Just update analytics for existing metadata
        existing = load_metadata(channel_dir)
        if not existing:
            print("❌ No existing metadata.json found. Run without --analytics-only first.")
            return

        from youtube_analytics.fetcher import get_video_id

        video_ids = [get_video_id(v.get("url", "")) for v in existing]
        video_ids = [vid for vid in video_ids if vid]
    else:
        # Fetch all videos from channel
        print(f"📥 Fetching all channel videos...")
        api_videos = fetch_all_channel_videos(youtube_service, uploads_playlist)
        video_ids = [v["video_id"] for v in api_videos]
        print(f"   Found {len(api_videos)} videos")

    # Fetch per-video analytics
    print(f"📊 Fetching per-video analytics for {len(video_ids)} videos...")
    analytics_data = fetch_analytics_per_video(analytics_service, video_ids, start_date)
    print(f"   Got analytics for {len(analytics_data)} videos")

    # Fetch transcripts if requested
    transcripts: dict[str, str] = {}
    if args.fetch_transcripts:
        missing_transcripts = []
        existing = load_metadata(channel_dir)
        existing_by_url = {}
        for v in existing:
            from youtube_analytics.fetcher import get_video_id as _gvid

            vid = _gvid(v.get("url", ""))
            if vid:
                existing_by_url[vid] = v

        for vid in video_ids:
            entry = existing_by_url.get(vid, {})
            if not entry.get("transcript"):
                missing_transcripts.append(vid)

        if missing_transcripts:
            print(f"📝 Fetching transcripts for {len(missing_transcripts)} videos...")
            transcripts = fetch_transcripts_for_videos(missing_transcripts)
            print(f"   Got {len(transcripts)} transcripts")

    # Fetch channel-level analytics
    print(f"📈 Fetching channel-level analytics...")
    channel_analytics = fetch_channel_level_analytics(
        analytics_service, start_date, channel_metadata
    )
    save_channel_analytics(channel_dir, channel_analytics)

    # Build/update metadata
    if args.analytics_only:
        updated = update_metadata_with_analytics(channel_dir, analytics_data, transcripts)
        print(f"✅ Updated {updated} videos in metadata.json")
    else:
        existing = load_metadata(channel_dir)
        full_metadata = build_metadata_from_all_videos(
            api_videos, analytics_data, existing, transcripts
        )
        save_metadata(channel_dir, full_metadata)
        print(f"✅ Saved {len(full_metadata)} videos to metadata.json")

    print(f"🎉 Sync complete for {title}")


def cmd_competitor(args: argparse.Namespace) -> None:
    """Fetch competitor channel data."""
    from youtube_analytics.auth import get_youtube_client
    from youtube_analytics.fetcher import fetch_competitor_channel_info, fetch_competitor_videos
    from youtube_analytics.storage import save_channel_info, save_metadata

    output_dir = Path(args.output_dir)

    print(f"🔑 Connecting with API key...")
    youtube = get_youtube_client(args.api_key)

    print(f"📡 Fetching channel info for {args.channel_id}...")
    channel_info = fetch_competitor_channel_info(youtube, args.channel_id)
    channel_info["last_refreshed"] = datetime.now().isoformat()
    save_channel_info(output_dir, channel_info)
    print(f"✅ Channel: {channel_info['title']} ({channel_info['subscriber_count']:,} subs)")

    print(f"📥 Fetching videos from last {args.months} months...")
    videos = fetch_competitor_videos(youtube, args.channel_id, months=args.months)

    # Save as metadata.json (same format, fewer fields)
    save_metadata(output_dir, videos)
    print(f"✅ Saved {len(videos)} videos to {output_dir}/metadata.json")

    shorts = [v for v in videos if v.get("is_short")]
    long_form = [v for v in videos if not v.get("is_short")]
    print(f"   Shorts: {len(shorts)} | Long-form: {len(long_form)}")


def cmd_export(args: argparse.Namespace) -> None:
    """Export channel data for LLM analysis."""
    from youtube_analytics.exporter import export_channel_snapshot

    channel_dir = Path(args.channel_dir)

    print(f"📄 Exporting channel snapshot ({args.format})...")
    content = export_channel_snapshot(channel_dir, fmt=args.format, top_n=args.top_n)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"✅ Saved to {output_path}")
    else:
        print(content)


def cmd_compare(args: argparse.Namespace) -> None:
    """Export competitive analysis."""
    from youtube_analytics.exporter import export_for_ideation

    own_dir = Path(args.own)
    competitor_dirs = [Path(c) for c in args.competitors]

    print(f"🔍 Generating competitive analysis...")
    content = export_for_ideation(own_dir, competitor_dirs)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"✅ Saved to {output_path}")
    else:
        print(content)


def cmd_insights(args: argparse.Namespace) -> None:
    """Print quick insights for a channel."""
    from youtube_analytics.analyzer import compute_insights, compute_summary
    from youtube_analytics.models import ChannelAnalytics, VideoMetrics
    from youtube_analytics.storage import load_channel_analytics, load_metadata

    channel_dir = Path(args.channel_dir)
    raw_metadata = load_metadata(channel_dir)

    if not raw_metadata:
        print(f"❌ No metadata.json found in {channel_dir}")
        return

    videos = [VideoMetrics.from_dict(v) for v in raw_metadata]
    raw_analytics = load_channel_analytics(channel_dir)
    channel_analytics = ChannelAnalytics.from_dict(raw_analytics) if raw_analytics else None

    summary = compute_summary(channel_dir.name, videos)
    insights = compute_insights(videos, channel_analytics)

    print(f"\n📊 CHANNEL: {summary.channel_name}")
    print("=" * 60)
    print(f"Videos: {summary.total_videos} (Shorts: {summary.total_shorts}, Long: {summary.total_long_form})")
    print(f"Total views: {summary.total_views:,}")
    print(f"Watch time: {summary.watch_time_hours:,.1f} hours")
    print(f"Net subscribers: +{summary.net_subscribers:,}")
    print(f"Avg retention: {summary.avg_retention_percentage}%")
    print(f"Avg engagement: {summary.avg_engagement_rate}%")
    print()

    for insight in insights:
        print(f"\n{insight['title']}")
        print(f"  {insight['description']}")
        data = insight.get("data", [])
        if isinstance(data, list):
            for item in data[:3]:
                if isinstance(item, dict):
                    summary_str = " | ".join(f"{k}: {v}" for k, v in item.items())
                    print(f"  • {summary_str}")
        elif isinstance(data, dict):
            for k, v in data.items():
                print(f"  • {k}: {v}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="youtube_analytics",
        description="YouTube channel analytics: sync, analyze, and export.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- sync ---
    sync_parser = subparsers.add_parser("sync", help="Sync own channel data")
    sync_parser.add_argument("--channel-dir", required=True, help="Path to channel data directory")
    sync_parser.add_argument("--secrets-dir", default="secrets", help="Path to secrets directory")
    sync_parser.add_argument("--analytics-only", action="store_true",
                             help="Only update analytics for existing videos")
    sync_parser.add_argument("--fetch-transcripts", action="store_true",
                             help="Fetch missing transcripts")
    sync_parser.set_defaults(func=cmd_sync)

    # --- competitor ---
    comp_parser = subparsers.add_parser("competitor", help="Fetch competitor channel data")
    comp_parser.add_argument("--channel-id", required=True, help="YouTube channel ID (UC...)")
    comp_parser.add_argument("--output-dir", required=True, help="Output directory for data")
    comp_parser.add_argument("--months", type=int, default=6, help="Months of history (default: 6)")
    comp_parser.add_argument("--api-key", default=None, help="YouTube Data API key")
    comp_parser.set_defaults(func=cmd_competitor)

    # --- export ---
    export_parser = subparsers.add_parser("export", help="Export channel snapshot for LLM")
    export_parser.add_argument("--channel-dir", required=True, help="Path to channel data directory")
    export_parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                               help="Output format (default: markdown)")
    export_parser.add_argument("--top-n", type=int, default=10, help="Number of top videos (default: 10)")
    export_parser.add_argument("--output", default=None, help="Output file path (prints to stdout if omitted)")
    export_parser.set_defaults(func=cmd_export)

    # --- compare ---
    compare_parser = subparsers.add_parser("compare", help="Competitive analysis")
    compare_parser.add_argument("--own", required=True, help="Own channel data directory")
    compare_parser.add_argument("--competitors", nargs="+", required=True,
                                help="Competitor data directories")
    compare_parser.add_argument("--output", default=None, help="Output file path")
    compare_parser.set_defaults(func=cmd_compare)

    # --- insights ---
    insights_parser = subparsers.add_parser("insights", help="Quick channel insights")
    insights_parser.add_argument("--channel-dir", required=True, help="Path to channel data directory")
    insights_parser.set_defaults(func=cmd_insights)

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
