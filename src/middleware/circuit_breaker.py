"""
Circuit breaker pattern for preventing cascading failures.

This module implements the circuit breaker pattern to prevent hammering
services that are experiencing issues, enabling graceful degradation.
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Service failing, reject requests
    HALF_OPEN = "half_open"    # Testing if service recovered


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    Transitions:
      CLOSED → OPEN: After N consecutive failures
      OPEN → HALF_OPEN: After timeout expires
      HALF_OPEN → CLOSED: If test call succeeds (2+ successes)
      HALF_OPEN → OPEN: If test call fails
    
    This prevents a failing service from being hammered with requests while
    it recovers, improving overall system resilience.
    
    Example:
        weather_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            service_name="OpenWeatherMap"
        )
        
        def fetch_weather(city):
            return weather_breaker.call(weather_client.get_temperature, city)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        service_name: str = "unknown"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening (default 5)
            recovery_timeout: Seconds to wait before attempting recovery (default 60)
            service_name: Name for logging and monitoring
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.service_name = service_name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0
        self.success_count_in_half_open = 0
    
    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result from func
            
        Raises:
            CircuitBreakerOpen: If circuit is OPEN
            Exception: Any exception from func
        """
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count_in_half_open = 0
                logger.info(
                    f"[{self.service_name}] Circuit HALF_OPEN, testing recovery"
                )
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker OPEN for {self.service_name}. "
                    f"Service unavailable, retrying in "
                    f"{int(self.recovery_timeout - (time.time() - self.last_failure_time))}s."
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_in_half_open += 1
            if self.success_count_in_half_open >= 2:  # 2 successes → CLOSED
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(
                    f"[{self.service_name}] Circuit CLOSED, service recovered"
                )
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.error(
                f"[{self.service_name}] Circuit OPEN again, recovery failed"
            )
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"[{self.service_name}] Circuit OPEN after {self.failure_count} failures"
            )
    
    def get_state(self) -> Dict[str, Any]:
        """Return circuit state for monitoring."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }
