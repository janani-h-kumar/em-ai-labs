"""Conversation timeline helpers for orchestration debugging."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.observability.tracing import get_span_id, get_trace_id

logger = logging.getLogger(__name__)

DEFAULT_PREVIEW_CHARS = 500


def preview_value(value: Any, max_chars: int = DEFAULT_PREVIEW_CHARS) -> str:
    """Return a compact, log-safe preview of an arbitrary value."""
    try:
        text = str(value)
    except Exception:
        text = f"<unprintable {type(value).__name__}>"

    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def timeline_event(
    *,
    session_id: str,
    node: str,
    event_type: str,
    status: str,
    thread_id: str | None = None,
    duration_ms: float | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a machine-readable event with trace correlation fields."""
    return {
        "event_id": str(uuid4()),
        "session_id": session_id,
        "thread_id": thread_id or session_id,
        "node": node,
        "event_type": event_type,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_ms": duration_ms,
        "trace_id": get_trace_id(),
        "span_id": get_span_id(),
        "attributes": attributes or {},
    }


def append_timeline_event(
    target: Any,
    *,
    session_id: str,
    node: str,
    event_type: str,
    status: str,
    thread_id: str | None = None,
    duration_ms: float | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an event to a dict state or ExecutionContext metadata timeline."""
    event = timeline_event(
        session_id=session_id,
        thread_id=thread_id,
        node=node,
        event_type=event_type,
        status=status,
        duration_ms=duration_ms,
        attributes=attributes,
    )

    if isinstance(target, dict):
        target.setdefault("timeline", []).append(event)
    else:
        metadata = getattr(target, "metadata", None)
        if isinstance(metadata, dict):
            metadata.setdefault("timeline", []).append(event)

    logger.info(
        "Timeline event",
        extra={
            "extra_data": {
                "session_id": session_id,
                "node": node,
                "event_type": event_type,
                "status": status,
                "duration_ms": duration_ms,
            }
        },
    )
    return event


class TimelineTimer:
    """Small timer context for consistent timeline durations."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 1)
