# YouTube Analytics

Shared Python package for YouTube channel analytics: sync, analyze, and export for LLM-driven content strategy.

## Install

```bash
# Editable install (recommended for development)
pip install -e /path/to/packages/youtube-analytics

# Or with dev dependencies
pip install -e "/path/to/packages/youtube-analytics[dev]"
```

## Usage

### CLI

```bash
# Sync own channel (requires OAuth client_secrets.json)
youtube-analytics sync --channel-dir channels/telugusampada --secrets-dir secrets/

# Sync analytics only (faster, no video discovery)
youtube-analytics sync --channel-dir channels/telugusampada --analytics-only

# Fetch competitor data (requires API key)
youtube-analytics competitor --channel-id UCxxxx --output-dir channels/competitor_name/ --months 6

# Export for LLM analysis
youtube-analytics export --channel-dir channels/telugusampada --format markdown --output snapshot.md

# Competitive analysis
youtube-analytics compare --own channels/telugusampada --competitors channels/comp1 channels/comp2

# Quick insights
youtube-analytics insights --channel-dir channels/telugusampada
```

### As a Library

```python
from youtube_analytics import (
    compute_insights,
    compute_summary,
    export_channel_snapshot,
    export_for_ideation,
    VideoMetrics,
)
from youtube_analytics.storage import load_metadata
from pathlib import Path

# Load existing channel data
videos = [VideoMetrics.from_dict(v) for v in load_metadata(Path("channels/telugusampada"))]

# Compute summary
summary = compute_summary("Telugu Sampada", videos)
print(f"Total views: {summary.total_views:,}")

# Generate LLM-ready export
snapshot = export_channel_snapshot(Path("channels/telugusampada"), fmt="markdown")
```

## Data Files

The module reads/writes three JSON files per channel:

| File | Content |
|------|---------|
| `metadata.json` | Per-video data (title, views, retention, engagement, transcript, tags) |
| `channel_analytics.json` | Traffic sources, geography, devices, demographics, daily trends |
| `channel_info.json` | Channel profile (title, subscribers, view count, keywords) |

## Auth Setup

### Own Channel (OAuth)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download as `client_secrets.json` into your secrets directory
4. Enable YouTube Analytics API and YouTube Data API v3

### Competitor Channels (API Key)

Set the `YOUTUBE_DATA_API_KEY` environment variable, or pass `--api-key` to the CLI.
