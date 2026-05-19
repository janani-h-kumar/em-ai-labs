"""
Retry middleware with exponential backoff and jitter.

This module provides decorators for automatic retry logic with exponential
backoff and jitter to handle transient failures gracefully.
"""

import time
import logging
import random
from functools import wraps
from typing import Callable, Any, TypeVar

logger = logging.getLogger(__name__)
F = TypeVar('F', bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter_factor: float = 0.1
) -> Callable[[F], F]:
    """
    Decorator for automatic retries with exponential backoff and jitter.
    
    Handles transient failures (network timeouts, temporary unavailability) by
    automatically retrying with increasing delays.
    
    Args:
        max_retries: Number of attempts (default 3, so 1 initial + 2 retries)
        base_delay: Initial delay in seconds (default 1.0)
        backoff_factor: Multiplier per retry (default 2.0, so 1s, 2s, 4s)
        jitter_factor: Random variance as fraction of delay (10% = 0.1)
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1)
        def fetch_weather(city):
            return weather_client.get_temperature(city)
        
        # Call will retry up to 3 times on failure with exponential backoff
        result = fetch_weather("New York")
    
    Returns:
        Decorated function with retry capability
        
    Raises:
        Last exception if all retries are exhausted
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempt {attempt + 1}/{max_retries}: {func.__name__}")
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Calculate delay with exponential backoff and jitter
                        delay = base_delay * (backoff_factor ** attempt)
                        jitter = delay * jitter_factor * (2 * random.random() - 1)
                        sleep_time = delay + jitter
                        
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}). "
                            f"Retrying in {sleep_time:.2f}s: {str(e)[:100]}"
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
            raise last_exception
        return wrapper  # type: ignore
    return decorator
