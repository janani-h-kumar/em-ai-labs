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
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any  # Fixed: Added missing import

from src.observability.tracing import get_span_id, get_trace_id
from src.utils.log_filters import PIIRedactionFilter

SERVICE_NAME = "em-ai-labs"
HOSTNAME = socket.gethostname()
ENVIRONMENT = os.getenv("ENV", "dev")

# Context variable for request correlation across async/threaded calls
correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class StructuredFormatter(logging.Formatter):
    """
    Format logs as JSON for easy aggregation and analysis in production.

    Output includes:
    - timestamp (ISO 8601 UTC)
    - level (DEBUG, INFO, WARNING, ERROR)
    - logger name
    - message
    - correlation_id (for request tracing)
    - service name
    - exception info (if present)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Fixed: Replaced deprecated utcnow() with zone-aware utc datetime
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _safe_message(record),
            "correlation_id": get_correlation_id() or "untracked",
            "trace_id": get_trace_id() or "untracked",
            "span_id": get_span_id() or "untracked",
            "log_version": 1,
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
            "host": HOSTNAME,
        }

        # Include extra fields if present, protecting core tracking keys from overrides
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            for key, value in record.extra_data.items():
                if key not in log_data:
                    log_data[key] = value
                else:
                    log_data[f"extra_{key}"] = value

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        return json.dumps(log_data, default=str)


def get_correlation_id() -> str | None:
    """
    Retrieve the current correlation ID.

    Fixed: Removed implicit generation mutation from here to keep formatting side-effect free.
    """
    return correlation_id.get()


def reset_correlation_id() -> None:
    """Call at the end of request processing to clear the context."""
    correlation_id.set(None)


def _safe_message(record: logging.LogRecord) -> str:
    try:
        return record.getMessage()
    except Exception as exc:
        return f"[LogFormatError] msg={record.msg!r} args={record.args!r} error={exc}"


def setup_structured_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,  # ← set False in CI / tests
    log_dir: str = "logs",
) -> None:
    # Initialize filter instance
    pii_filter = PIIRedactionFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    # Fixed: Added filter to console to protect stdout logs in container aggregators
    console_handler.addFilter(pii_filter)

    handlers: list[logging.Handler] = [console_handler]

    if log_to_file:
        Path(log_dir).mkdir(exist_ok=True)
        file_handler = RotatingFileHandler(
            f"{log_dir}/orchestrator.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.addFilter(pii_filter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Safely clean out old handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    for h in handlers:
        root_logger.addHandler(h)

    logging.getLogger("httpx").setLevel(logging.WARNING)


def set_correlation_id(request_id: str | None = None) -> str:
    """
    Set or generate correlation ID for request tracing.

    Args:
        request_id: Optional request ID. If None, generates a new UUID.

    Returns:
        The correlation ID (newly generated or provided)
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
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    if extra_data:
        logger_obj.log(log_level, message, extra={"extra_data": extra_data})
    else:
        logger_obj.log(log_level, message)
