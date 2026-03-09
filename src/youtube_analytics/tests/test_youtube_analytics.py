"""
Tests for youtube_analytics module.

Uses fixture data derived from the existing telugusampada channel data.
No live YouTube API calls.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from youtube_analytics.analyzer import compare_with_competitors, compute_insights, compute_summary, rank_videos
from youtube_analytics.exporter import export_channel_snapshot, export_for_ideation
from youtube_analytics.models import (
    ChannelAnalytics,
    ChannelProfile,
    ChannelSummary,
    CompetitorVideo,
    VideoMetrics,
)
from youtube_analytics.storage import (
    build_metadata_from_all_videos,
    load_channel_analytics,
    load_channel_info,
    load_metadata,
    save_channel_analytics,
    save_channel_info,
    save_metadata,
    update_metadata_with_analytics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VIDEO_DICT = {
    "title": "Test Video - Health Tips",
    "url": "https://www.youtube.com/watch?v=abc12345678",
    "description": "A test video about health",
    "published_at": "2026-02-08T12:29:43Z",
    "tags": ["health", "tips", "telugu"],
    "transcript": "This is a sample transcript",
    "duration_seconds": 55,
    "thumbnail": "https://i.ytimg.com/vi/abc12345678/maxresdefault.jpg",
    "category": "Education",
    "is_short": True,
    "views": 3518895,
    "estimated_minutes_watched": 1207800,
    "average_view_duration_seconds": 44,
    "average_view_percentage": 79.78,
    "subscribers_gained": 5904,
    "subscribers_lost": 193,
    "likes": 75988,
    "dislikes": 2696,
    "comments": 120,
    "shares": 83299,
    "engaged_views": 1583976,
    "videos_added_to_playlists": 9164,
    "videos_removed_from_playlists": 1921,
    "last_refreshed": "2026-03-06T09:48:58.192964",
}

SAMPLE_VIDEO_DICT_2 = {
    "title": "Test Video 2 - Cooking Guide",
    "url": "https://www.youtube.com/watch?v=def98765432",
    "description": "Another test video",
    "published_at": "2026-02-10T07:34:31Z",
    "tags": ["cooking", "kitchen", "tips"],
    "transcript": "Another transcript",
    "duration_seconds": 320,
    "is_short": False,
    "views": 150000,
    "estimated_minutes_watched": 50000,
    "average_view_duration_seconds": 200,
    "average_view_percentage": 62.5,
    "subscribers_gained": 200,
    "subscribers_lost": 10,
    "likes": 5000,
    "comments": 50,
    "shares": 500,
    "engaged_views": 70000,
    "last_refreshed": "2026-03-06T09:48:58.192964",
}

SAMPLE_CHANNEL_INFO = {
    "channel_id": "UC-MIwInt031gtXSkujMyNTA",
    "title": "Telugu Sampada",
    "description": "Test channel description",
    "subscriber_count": 58400,
    "view_count": 27729279,
    "video_count": 63,
    "country": "IN",
    "last_refreshed": "2026-03-06T09:48:55.488101",
}

SAMPLE_CHANNEL_ANALYTICS = {
    "last_refreshed": "2026-03-06T09:48:58.200934",
    "traffic_sources": [
        {"insightTrafficSourceType": "SHORTS", "views": 21719956, "estimatedMinutesWatched": 5647254},
        {"insightTrafficSourceType": "SUBSCRIBER", "views": 1880459, "estimatedMinutesWatched": 1147545},
        {"insightTrafficSourceType": "YT_SEARCH", "views": 636031, "estimatedMinutesWatched": 155616},
    ],
    "top_countries": [
        {"country": "IN", "views": 25432427, "subscribersGained": 55435},
        {"country": "US", "views": 59588, "subscribersGained": 67},
    ],
    "subscribed_breakdown": [
        {"subscribedStatus": "UNSUBSCRIBED", "views": 24784407},
        {"subscribedStatus": "SUBSCRIBED", "views": 878084},
    ],
    "device_types": [],
    "operating_systems": [],
    "demographics": [],
    "sharing_services": [
        {"sharingService": "WHATS_APP", "shares": 246270},
    ],
    "daily_trends": [],
}


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestVideoMetrics:
    def test_from_dict(self) -> None:
        vm = VideoMetrics.from_dict(SAMPLE_VIDEO_DICT)
        assert vm.title == "Test Video - Health Tips"
        assert vm.video_id == "abc12345678"
        assert vm.views == 3518895
        assert vm.is_short is True
        assert len(vm.tags) == 3

    def test_engagement_rate(self) -> None:
        vm = VideoMetrics.from_dict(SAMPLE_VIDEO_DICT)
        expected = round((75988 + 120 + 83299) / 3518895 * 100, 2)
        assert vm.engagement_rate == expected

    def test_subscriber_efficiency(self) -> None:
        vm = VideoMetrics.from_dict(SAMPLE_VIDEO_DICT)
        expected = round(5904 / 3518895 * 1000, 2)
        assert vm.subscriber_efficiency == expected

    def test_share_rate(self) -> None:
        vm = VideoMetrics.from_dict(SAMPLE_VIDEO_DICT)
        expected = round(83299 / 3518895 * 1000, 2)
        assert vm.share_rate == expected

    def test_net_subscribers(self) -> None:
        vm = VideoMetrics.from_dict(SAMPLE_VIDEO_DICT)
        assert vm.net_subscribers == 5904 - 193

    def test_zero_views_no_division_error(self) -> None:
        vm = VideoMetrics(title="Empty", url="", views=0)
        assert vm.engagement_rate == 0.0
        assert vm.subscriber_efficiency == 0.0
        assert vm.share_rate == 0.0

    def test_video_id_extraction(self) -> None:
        vm = VideoMetrics.from_dict({"url": "https://www.youtube.com/shorts/xyz12345678"})
        assert vm.video_id == "xyz12345678"


class TestChannelProfile:
    def test_from_dict(self) -> None:
        cp = ChannelProfile.from_dict(SAMPLE_CHANNEL_INFO)
        assert cp.title == "Telugu Sampada"
        assert cp.subscriber_count == 58400

    def test_to_dict_roundtrip(self) -> None:
        cp = ChannelProfile.from_dict(SAMPLE_CHANNEL_INFO)
        d = cp.to_dict()
        assert d["title"] == "Telugu Sampada"
        assert d["subscriber_count"] == 58400


class TestChannelAnalytics:
    def test_from_dict(self) -> None:
        ca = ChannelAnalytics.from_dict(SAMPLE_CHANNEL_ANALYTICS)
        assert len(ca.traffic_sources) == 3
        assert ca.traffic_sources[0]["insightTrafficSourceType"] == "SHORTS"
        assert len(ca.top_countries) == 2


class TestCompetitorVideo:
    def test_engagement_rate(self) -> None:
        cv = CompetitorVideo(view_count=10000, like_count=500, comment_count=50)
        assert cv.engagement_rate == 5.5

    def test_to_dict(self) -> None:
        cv = CompetitorVideo(video_id="test123", title="Test", view_count=1000)
        d = cv.to_dict()
        assert d["video_id"] == "test123"
        assert d["view_count"] == 1000


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStorage:
    def test_metadata_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data = [SAMPLE_VIDEO_DICT, SAMPLE_VIDEO_DICT_2]
            save_metadata(Path(tmpdir), data)
            loaded = load_metadata(Path(tmpdir))
            assert len(loaded) == 2
            assert loaded[0]["title"] == SAMPLE_VIDEO_DICT["title"]

    def test_channel_analytics_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            save_channel_analytics(Path(tmpdir), SAMPLE_CHANNEL_ANALYTICS)
            loaded = load_channel_analytics(Path(tmpdir))
            assert len(loaded["traffic_sources"]) == 3

    def test_channel_info_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            save_channel_info(Path(tmpdir), SAMPLE_CHANNEL_INFO)
            loaded = load_channel_info(Path(tmpdir))
            assert loaded["title"] == "Telugu Sampada"

    def test_load_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert load_metadata(Path(tmpdir)) == []
            assert load_channel_analytics(Path(tmpdir)) == {}
            assert load_channel_info(Path(tmpdir)) == {}

    def test_update_metadata_with_analytics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            save_metadata(Path(tmpdir), [SAMPLE_VIDEO_DICT])
            analytics = {"abc12345678": {"views": 9999999, "likes": 100000}}
            updated = update_metadata_with_analytics(Path(tmpdir), analytics)
            assert updated == 1

            reloaded = load_metadata(Path(tmpdir))
            assert reloaded[0]["views"] == 9999999

    def test_build_metadata_from_all_videos(self) -> None:
        api_videos = [
            {"video_id": "abc12345678", "title": "Video 1", "url": "https://youtube.com/watch?v=abc12345678"},
            {"video_id": "new23456789", "title": "Video 2", "url": "https://youtube.com/watch?v=new23456789"},
        ]
        analytics = {
            "abc12345678": {"views": 5000, "likes": 100},
            "new23456789": {"views": 3000, "likes": 50},
        }
        existing = [SAMPLE_VIDEO_DICT]

        result = build_metadata_from_all_videos(api_videos, analytics, existing)
        assert len(result) == 2
        # Existing tags should be preserved
        preserved = next(v for v in result if "abc12345678" in v.get("url", ""))
        assert preserved.get("tags") == ["health", "tips", "telugu"]
        # Should be sorted by views descending
        assert result[0]["views"] >= result[1]["views"]


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------

class TestAnalyzer:
    def _make_videos(self) -> list[VideoMetrics]:
        return [
            VideoMetrics.from_dict(SAMPLE_VIDEO_DICT),
            VideoMetrics.from_dict(SAMPLE_VIDEO_DICT_2),
        ]

    def test_compute_summary(self) -> None:
        videos = self._make_videos()
        summary = compute_summary("test_channel", videos)
        assert summary.total_videos == 2
        assert summary.total_shorts == 1
        assert summary.total_long_form == 1
        assert summary.total_views == 3518895 + 150000
        assert summary.net_subscribers > 0
        assert summary.watch_time_hours > 0

    def test_rank_videos_by_views(self) -> None:
        videos = self._make_videos()
        ranked = rank_videos(videos, sort_by="views", limit=10)
        assert len(ranked) == 2
        assert ranked[0]["rank"] == 1
        assert ranked[0]["views"] > ranked[1]["views"]

    def test_rank_videos_by_retention(self) -> None:
        videos = self._make_videos()
        ranked = rank_videos(videos, sort_by="retention", limit=10)
        assert ranked[0]["retention"] >= ranked[1]["retention"]

    def test_compute_insights(self) -> None:
        videos = self._make_videos()
        ca = ChannelAnalytics.from_dict(SAMPLE_CHANNEL_ANALYTICS)
        insights = compute_insights(videos, ca)
        assert len(insights) > 0

        # Check we get expected insight types
        types = {i["type"] for i in insights}
        assert "top_performers" in types
        assert "content_format" in types

    def test_compare_with_competitors(self) -> None:
        own = self._make_videos()
        comp_vids = [
            CompetitorVideo(video_id="c1", title="Comp 1", view_count=5000, like_count=200, tags=["new_tag"]),
            CompetitorVideo(video_id="c2", title="Comp 2", view_count=3000, like_count=100, tags=["health"]),
        ]
        result = compare_with_competitors(own, {"competitor1": comp_vids})
        assert "own_channel" in result
        assert "competitor1" in result["competitors"]
        assert result["competitors"]["competitor1"]["total_videos"] == 2
        # "new_tag" is unique to competitor
        assert "new_tag" in result["competitors"]["competitor1"]["unique_tags"]


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------

class TestExporter:
    def _setup_channel_dir(self, tmpdir: str) -> Path:
        """Create a temp channel directory with sample data."""
        channel_dir = Path(tmpdir)
        save_metadata(channel_dir, [SAMPLE_VIDEO_DICT, SAMPLE_VIDEO_DICT_2])
        save_channel_analytics(channel_dir, SAMPLE_CHANNEL_ANALYTICS)
        save_channel_info(channel_dir, SAMPLE_CHANNEL_INFO)
        return channel_dir

    def test_export_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            channel_dir = self._setup_channel_dir(tmpdir)
            output = export_channel_snapshot(channel_dir, fmt="markdown")
            assert "# Channel Snapshot:" in output
            assert "Test Video - Health Tips" in output
            assert "Performance Summary" in output

    def test_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            channel_dir = self._setup_channel_dir(tmpdir)
            output = export_channel_snapshot(channel_dir, fmt="json")
            data = json.loads(output)
            assert "summary" in data
            assert data["summary"]["total_videos"] == 2
            assert len(data["top_videos"]) > 0

    def test_export_for_ideation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            channel_dir = self._setup_channel_dir(tmpdir)
            output = export_for_ideation(channel_dir)
            assert "Content Strategy Brief" in output
            assert "What's Working Well" in output
            assert "Areas for Improvement" in output
            assert "Questions to Answer" in output
