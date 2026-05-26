"""
Structured logging utilities for production observability.

Provides JSON-formatted logging with correlation IDs for request tracing
and production debugging.
"""

import contextvars
import json
import logging
import os
import socket
import sys
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Path("logs").mkdir(exist_ok=True)

SERVICE_NAME = "em-ai-labs"
HOSTNAME = socket.gethostname()
ENVIRONMENT = os.getenv("ENV", "dev")

# Context variable for request correlation across async/threaded calls
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default=None)


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
            "correlation_id": get_correlation_id(),
            "log_version": 1,
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
            "host": HOSTNAME,
        }

        # Include extra fields if present
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        return json.dumps(log_data, default=str)


def get_correlation_id() -> str:
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid


def setup_structured_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,  # ← set False in CI / tests
    log_dir: str = "logs",
) -> None:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())

    handlers: list[logging.Handler] = [console_handler]

    if log_to_file:
        Path(log_dir).mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            f"{log_dir}/orchestrator.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(StructuredFormatter())
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    for h in handlers:
        root_logger.addHandler(h)


def set_correlation_id(request_id: str | None = None) -> str:
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


def log_with_context(
    logger_obj: logging.Logger, level: str, message: str, **extra_data: Any
) -> None:
    """
    Log message with extra context data.

    Args:
        logger_obj: Logger instance
        level: Level name (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        **extra_data: Additional fields to include in JSON output

    Example:
        log_with_context(logger, "INFO", "Request completed", tokens=150, latency_ms=245.5)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    if extra_data:
        logger_obj.log(log_level, message, extra={"extra_data": extra_data})
    else:
        logger_obj.log(log_level, message)
