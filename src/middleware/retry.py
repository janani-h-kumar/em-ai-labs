"""
Retry middleware with exponential backoff, jitter, and error filtering.

Changes from original:
- Added retryable_exceptions parameter: only transient errors are retried
  (timeouts, connection errors, 5xx). Permanent failures like CityNotFoundError
  or invalid API keys (401/404) now fail immediately instead of wasting
  3 retry attempts on an error that will never succeed.
- Default retryable set covers the most common transient cases.
"""

import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

# Errors that are worth retrying — transient network/infra problems.
# Import lazily to avoid circular imports; add your own as needed.
_DEFAULT_RETRYABLE: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter_factor: float = 0.1,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for automatic retries with exponential backoff and jitter.

    Only retries on transient errors. Permanent errors (bad API key,
    city not found, bad request) fail immediately on the first attempt.

    Args:
        max_retries: Total number of attempts including the first (default 3)
        base_delay: Initial delay in seconds (default 1.0)
        backoff_factor: Delay multiplier per retry (default 2.0 → 1s, 2s, 4s)
        jitter_factor: Random variance as fraction of delay (default 0.1 = ±10%)
        retryable_exceptions: Tuple of exception types to retry on.
            Defaults to (ConnectionError, TimeoutError, OSError).
            Pass a custom tuple to restrict or broaden retry behaviour.

    Example:
        import requests
        from src.tools.weather_tool import WeatherAPIError

        @retry_with_backoff(
            max_retries=3,
            retryable_exceptions=(requests.Timeout, requests.ConnectionError)
        )
        def fetch_data():
            ...

    Returns:
        Decorated function with selective retry capability

    Raises:
        Last exception if all retries are exhausted, or immediately if
        the exception is not in retryable_exceptions.
    """
    effective_retryable = retryable_exceptions or _DEFAULT_RETRYABLE

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    logger.debug("Attempt %d/%d: %s", attempt + 1, max_retries, func.__name__)
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # FIX: Don't retry permanent failures — fail fast.
                    if not isinstance(e, effective_retryable):
                        logger.debug(
                            "%s raised non-retryable " "%s, failing immediately.",
                            func.__name__,
                            type(e).__name__,
                        )
                        raise

                    if attempt < max_retries - 1:
                        delay = base_delay * (backoff_factor**attempt)
                        jitter = delay * jitter_factor * (2 * random.random() - 1)
                        sleep_time = max(0.0, delay + jitter)
                        logger.warning(
                            "%s failed (attempt %d/%d), " "retrying in %.2f}s: %s",
                            func.__name__,
                            attempt + 1,
                            max_retries,
                            sleep_time,
                            str(e)[:100],
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s", func.__name__, max_retries, e
                        )
            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
