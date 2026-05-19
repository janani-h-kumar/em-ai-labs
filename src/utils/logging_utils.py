"""
Structured logging utilities for production observability.

Provides JSON-formatted logging with correlation IDs for request tracing
and production debugging.
"""

import json
import logging
import uuid
import contextvars
from datetime import datetime
from typing import Optional, Dict, Any

# Context variable for request correlation across async/threaded calls
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'correlation_id',
    default=str(uuid.uuid4())
)


class StructuredFormatter(logging.Formatter):
    """
    Format logs as JSON for easy aggregation and analysis in production.
    
    Output includes:
    - timestamp (ISO 8601)
    - level (DEBUG, INFO, WARNING, ERROR)
    - logger name
    - message
    - correlation_id (for request tracing)
    - service name
    - exception info (if present)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
            "service": "em-ai-labs",
        }
        
        # Include extra fields if present
        if hasattr(record, 'extra_data') and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)
        
        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        
        return json.dumps(log_data, default=str)


def setup_structured_logging(log_level: str = "INFO") -> None:
    """
    Initialize structured JSON logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Example:
        from src.utils.logging_utils import setup_structured_logging
        setup_structured_logging("DEBUG")
    """
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    
    root_logger.addHandler(handler)
    
    logger = logging.getLogger(__name__)
    logger.info("Structured logging initialized", extra={"extra_data": {"level": log_level}})


def set_correlation_id(request_id: Optional[str] = None) -> str:
    """
    Set or generate correlation ID for request tracing.
    
    Args:
        request_id: Optional request ID. If None, generates a new UUID.
    
    Returns:
        The correlation ID (newly generated or provided)
    
    Example:
        request_id = set_correlation_id("user-123-weather-query")
        # Now all log entries will include this request_id
        logger.info("Processing weather request")  # Will have correlation_id in JSON
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    correlation_id.set(request_id)
    return request_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id.get()


def log_with_context(
    logger_obj: logging.Logger,
    level: str,
    message: str,
    **extra_data: Any
) -> None:
    """
    Log message with extra context data.
    
    Args:
        logger_obj: Logger instance
        level: Level name (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **extra_data: Additional fields to include in JSON output
    
    Example:
        log_with_context(logger, "INFO", "Request completed", 
                        tokens=150, latency_ms=245.5)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    if extra_data:
        logger_obj.log(log_level, message, extra={"extra_data": extra_data})
    else:
        logger_obj.log(log_level, message)
