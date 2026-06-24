"""
OpenTelemetry tracing setup for em-ai-labs.

This module exposes a single tracer plus helper functions for trace ID
and span ID propagation. It is intentionally safe to import even when
OpenTelemetry exporters are not installed or configured.
"""

import logging
import os
import threading
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)

_SERVICE_NAME = "em-ai-labs"
_request_count = 0
_request_count_lock = threading.Lock()


def setup_tracing(service_name: str = _SERVICE_NAME) -> trace.Tracer:
    """Initialise and return a tracer.

    If OTEL_EXPORTER_OTLP_ENDPOINT is configured, this wire up the OTLP
    exporter. Otherwise the NoOp tracer is returned.
    """
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — using NoOp tracer")
        return trace.get_tracer(service_name)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry tracing enabled — exporting to %s", endpoint)
    except ImportError:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the OTLP exporter is not installed — falling back to NoOp tracer"
        )
    except Exception:
        logger.exception(
            "Failed to initialise OTel exporter for endpoint=%s — falling back to NoOp tracer",
            endpoint,
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
