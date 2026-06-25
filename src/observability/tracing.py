"""
OpenTelemetry tracing setup for em-ai-labs.

This module exposes a single tracer plus helper functions for trace ID
and span ID propagation. It is intentionally safe to import even when
OpenTelemetry exporters are not installed or configured.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ReadableSpan,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_SERVICE_NAME = "em-ai-labs"
_request_count = 0
_request_count_lock = threading.Lock()


def _load_trace_env() -> None:
    """Load local env files before tracing decides whether to export."""
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    app_env = (os.getenv("APP_ENV") or "dev").lower()
    load_dotenv(repo_root / f".env.{app_env}", override=False)


class JsonlSpanExporter(SpanExporter):
    """Write completed spans to a local JSONL file for offline inspection."""

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        try:
            with self._lock:
                with self.file_path.open("a", encoding="utf-8") as trace_file:
                    for span in spans:
                        trace_file.write(json.dumps(_span_to_json(span), default=str))
                        trace_file.write("\n")
            return SpanExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to export spans to %s", self.file_path)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        return None


def _span_to_json(span: ReadableSpan) -> dict[str, Any]:
    context = span.get_span_context()
    parent = span.parent
    return {
        "name": span.name,
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent else None,
        "start_time_unix_nano": span.start_time,
        "end_time_unix_nano": span.end_time,
        "duration_ms": _duration_ms(span),
        "status": {
            "status_code": span.status.status_code.name,
            "description": span.status.description,
        },
        "attributes": dict(span.attributes or {}),
        "events": [
            {
                "name": event.name,
                "timestamp_unix_nano": event.timestamp,
                "attributes": dict(event.attributes or {}),
            }
            for event in span.events
        ],
        "resource": dict(span.resource.attributes),
    }


def _duration_ms(span: ReadableSpan) -> float | None:
    if span.start_time is None or span.end_time is None:
        return None
    return round((span.end_time - span.start_time) / 1_000_000, 3)


def setup_tracing(service_name: str = _SERVICE_NAME) -> trace.Tracer:
    """Initialise and return a tracer.

    OTEL_TRACES_EXPORTER controls export mode:
    - file: write spans to OTEL_TRACE_FILE as JSONL
    - otlp: export spans to OTEL_EXPORTER_OTLP_ENDPOINT
    - none/unset: return the NoOp tracer
    """
    _load_trace_env()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter_mode = os.getenv("OTEL_TRACES_EXPORTER") or ("otlp" if endpoint else "none")
    exporter_mode = exporter_mode.strip().lower()
    resource = Resource.create({"service.name": service_name})

    if exporter_mode in ("", "none", "noop", "false", "0"):
        logger.info("OTEL_TRACES_EXPORTER not set - using NoOp tracer")
        return trace.get_tracer(service_name)

    try:
        provider = TracerProvider(resource=resource)

        if exporter_mode == "file":
            trace_file = os.getenv("OTEL_TRACE_FILE", "logs/traces.jsonl")
            provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(trace_file)))
            trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry tracing enabled - exporting JSONL to %s", trace_file)
            return trace.get_tracer(service_name)

        if exporter_mode == "otlp":
            if not endpoint:
                logger.warning(
                    "OTEL_TRACES_EXPORTER=otlp but OTEL_EXPORTER_OTLP_ENDPOINT is unset - using NoOp tracer"
                )
                return trace.get_tracer(service_name)

            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry tracing enabled - exporting OTLP to %s", endpoint)
            return trace.get_tracer(service_name)

        logger.warning("Unsupported OTEL_TRACES_EXPORTER=%s - using NoOp tracer", exporter_mode)
    except ImportError:
        logger.warning(
            "OTEL_TRACES_EXPORTER=otlp but the OTLP exporter is not installed - falling back to NoOp tracer"
        )
    except Exception:
        logger.exception(
            "Failed to initialise OTel exporter mode=%s - falling back to NoOp tracer",
            exporter_mode,
        )

    return trace.get_tracer(service_name)


tracer = setup_tracing()


class SpanContextManager:
    def __init__(self, name: str, attributes: dict[str, Any]) -> None:
        self._manager = tracer.start_as_current_span(name)
        self._attributes = attributes

    def __enter__(self):
        span = self._manager.__enter__()
        for key, value in self._attributes.items():
            try:
                span.set_attribute(key, value)
            except Exception:
                logger.exception("Failed to set trace attribute %s=%s", key, value)
        return span

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._manager.__exit__(exc_type, exc_val, exc_tb)


def create_span(name: str, **attributes: Any):
    """Create a span context manager with attributes set."""
    return SpanContextManager(name, attributes)


def increment_request_count() -> int:
    """Increment and return the total request count."""
    global _request_count
    with _request_count_lock:
        _request_count += 1
        return _request_count


def get_request_count() -> int:
    """Return the current request count."""
    with _request_count_lock:
        return _request_count


def get_trace_id() -> str | None:
    """Return the active trace ID as a hex string, or None."""
    span = trace.get_current_span()
    if not span or span.get_span_context().trace_id == 0:
        return None
    return format(span.get_span_context().trace_id, "032x")


def get_span_id() -> str | None:
    """Return the active span ID as a hex string, or None."""
    span = trace.get_current_span()
    if not span or not span.get_span_context().is_valid:
        return None
    return format(span.get_span_context().span_id, "016x")
