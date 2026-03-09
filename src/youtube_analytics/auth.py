"""
OAuth and API-key authentication for YouTube APIs.

Provides two auth strategies:
- OAuth (own channel): full access to Analytics + Data APIs
- API key (competitor): read-only access to public Data API
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# YouTube Analytics API requires these scopes
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

_DEFAULT_CLIENT_SECRETS = "client_secrets.json"
_DEFAULT_TOKEN_FILE = "youtube_token_analytics.json"


class YouTubeAuthError(Exception):
    """Raised when YouTube authentication fails."""


def _find_available_port(start_port: int = 8090, max_attempts: int = 10) -> int:
    """Find an available port for the OAuth callback server."""
    for i in range(max_attempts):
        port = start_port + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    msg = f"No available port in range {start_port}-{start_port + max_attempts - 1}"
    raise OSError(msg)


def get_authenticated_services(
    secrets_dir: Path,
    *,
    client_secrets_file: str = _DEFAULT_CLIENT_SECRETS,
    token_file: str = _DEFAULT_TOKEN_FILE,
) -> tuple[Any, Any]:
    """Authenticate and return YouTube Analytics + Data API services via OAuth.

    Loads existing OAuth token, refreshes if expired, or initiates a new
    browser-based OAuth flow if no valid token exists.

    Args:
        secrets_dir: Path to directory containing client_secrets.json and token file.
        client_secrets_file: Filename for OAuth client credentials.
        token_file: Filename for the cached OAuth token.

    Returns:
        Tuple of (youtube_analytics_service, youtube_data_service).

    Raises:
        YouTubeAuthError: If authentication cannot be completed.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        msg = (
            "Missing YouTube API dependencies. Install with: "
            "pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )
        raise YouTubeAuthError(msg) from e

    secrets_path = Path(secrets_dir)
    client_file = secrets_path / client_secrets_file
    token_path = secrets_path / token_file

    if not secrets_path.exists():
        msg = f"Secrets directory not found: {secrets_path}"
        raise YouTubeAuthError(msg)

    creds = None

    # Load existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        logger.debug("Loaded existing analytics token from %s", token_path.name)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired access token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                error_msg = str(e).lower()
                if any(kw in error_msg for kw in ("invalid_grant", "expired", "revoked")):
                    logger.warning("Refresh token expired or revoked, re-authenticating")
                    token_path.unlink(missing_ok=True)
                    creds = None
                else:
                    raise

        if not creds or not creds.valid:
            if not client_file.exists():
                msg = (
                    f"Client secrets not found: {client_file}. "
                    "Download from Google Cloud Console → APIs & Services → Credentials"
                )
                raise YouTubeAuthError(msg)

            logger.info("Opening browser for OAuth consent...")
            port = _find_available_port()
            flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
            creds = flow.run_local_server(port=port)

        # Save token
        secrets_path.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        logger.info("Analytics token saved: %s", token_path.name)

    analytics = build("youtubeAnalytics", "v2", credentials=creds)
    youtube = build("youtube", "v3", credentials=creds)

    return analytics, youtube


def get_youtube_client(api_key: str | None = None) -> Any:
    """Build YouTube Data API v3 client with API key (for competitor/public data).

    Args:
        api_key: Google API key. If None, reads from YOUTUBE_DATA_API_KEY
                 or GOOGLE_GEMINI_API_KEY env vars.

    Returns:
        YouTube Data API resource.

    Raises:
        YouTubeAuthError: If no API key is available.
    """
    import os

    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        msg = "Missing dependency: pip install google-api-python-client"
        raise YouTubeAuthError(msg) from e

    if not api_key:
        api_key = os.environ.get("YOUTUBE_DATA_API_KEY") or os.environ.get("GOOGLE_GEMINI_API_KEY")

    if not api_key:
        msg = (
            "No API key provided. Set YOUTUBE_DATA_API_KEY or GOOGLE_GEMINI_API_KEY "
            "environment variable, or pass api_key parameter."
        )
        raise YouTubeAuthError(msg)

    return build("youtube", "v3", developerKey=api_key)
