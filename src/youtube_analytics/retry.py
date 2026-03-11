"""
Retry logic with exponential backoff for YouTube API calls.

Handles transient errors (429, 500, 503) from the YouTube API
and yt-dlp subprocess calls.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that are transient and worth retrying
RETRYABLE_STATUS_CODES = {429, 500, 503}


def retry_api_call(
    fn: Callable[..., T] | None = None,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable[..., T]:
    """Decorator: retry a function on transient YouTube API errors.

    Uses exponential backoff: delay = base_delay * 2^attempt (capped at max_delay).
    Retries on HttpError with retryable status codes, or on ConnectionError/TimeoutError.

    Usage:
        @retry_api_call
        def my_api_call():
            ...

        @retry_api_call(max_retries=5, base_delay=2.0)
        def another_call():
            ...

    Args:
        fn: The function to wrap (auto-filled by decorator).
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.

    Returns:
        Wrapped function with retry logic.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not _is_retryable(e):
                        raise

                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            "Retryable error on attempt %d/%d for %s: %s. "
                            "Retrying in %.1fs...",
                            attempt + 1,
                            max_retries + 1,
                            func.__name__,
                            e,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d retries exhausted for %s: %s",
                            max_retries + 1,
                            func.__name__,
                            e,
                        )

            raise last_exception  # type: ignore[misc]

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator  # type: ignore[return-value]


def _is_retryable(error: Exception) -> bool:
    """Check if an error is transient and worth retrying.

    Args:
        error: The exception to check.

    Returns:
        True if the error is retryable.
    """
    # Google API HttpError
    if hasattr(error, "resp") and hasattr(error.resp, "status"):
        return error.resp.status in RETRYABLE_STATUS_CODES

    # Connection and timeout errors
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True

    # Check error message for known transient patterns
    msg = str(error).lower()
    retryable_patterns = [
        "rate limit",
        "quota exceeded",
        "too many requests",
        "service unavailable",
        "internal error",
        "backend error",
    ]
    return any(pattern in msg for pattern in retryable_patterns)
