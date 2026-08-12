"""OpenTelemetry tracing setup for em-ai-labs.

P0 observability is intentionally trace-only:

    Agent framework -> OpenTelemetry SDK -> OTLP -> Jaeger

There is no custom trace file exporter, dashboard, database, Prometheus, or
Loki integration in the application. Local development uses Jaeger's OTLP
receiver by default at http://localhost:4317.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Mapping
from typing import Any

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

logger = logging.getLogger(__name__)

SERVICE_NAME = "em-ai-labs"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"

_request_count = 0
_request_count_lock = threading.Lock()
_provider_initialized = False


def _load_trace_env() -> None:
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    app_env = (os.getenv("APP_ENV") or "dev").lower()
    load_dotenv(repo_root / f".env.{app_env}", override=False)


def _build_resource(service_name: str) -> Resource:
    return Resource.create(
        {
            "service.name": service_name,
            "deployment.environment.name": os.getenv("ENV", "dev"),
        }
    )


def setup_tracing(service_name: str = SERVICE_NAME) -> trace.Tracer:
    """Configure the process-wide OpenTelemetry provider.

    ``OTEL_TRACES_EXPORTER=none`` explicitly disables export for tests.
    Otherwise OTLP/gRPC is used, defaulting to Jaeger at localhost:4317.
    """
    global _provider_initialized

    _load_trace_env()

    if _provider_initialized:
        return trace.get_tracer(service_name)

    exporter_mode = (os.getenv("OTEL_TRACES_EXPORTER") or "otlp").strip().lower()
    if exporter_mode in {"none", "noop", "false", "0"} or exporter_mode not in {"otlp", "otlp/grpc", "grpc"}:
        if exporter_mode not in {"none", "noop", "false", "0"}:
            logger.warning(
                "Unsupported OTEL_TRACES_EXPORTER=%s; trace export disabled",
                exporter_mode,
            )
        provider = TracerProvider(resource=_build_resource(service_name))
        trace.set_tracer_provider(provider)
        _provider_initialized = True
        logger.info("OpenTelemetry tracing enabled without an exporter")
        return trace.get_tracer(service_name)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    provider = TracerProvider(resource=_build_resource(service_name))
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider_initialized = True

    logger.info("OpenTelemetry tracing enabled; OTLP endpoint=%s", endpoint)
    return trace.get_tracer(service_name)


tracer = setup_tracing()


class SpanContextManager:
    """Context manager that creates a current OpenTelemetry span."""

    def __init__(self, name: str, attributes: Mapping[str, Any]) -> None:
        self._manager = tracer.start_as_current_span(name)
        self._attributes = attributes

    def __enter__(self):
        span = self._manager.__enter__()
        _set_attributes(span, self._attributes)
        return span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            span = trace.get_current_span()
            if span.get_span_context().is_valid:
                span.set_attribute("outcome", "error")
                span.set_attribute("error.type", type(exc_val).__name__)
        return self._manager.__exit__(exc_type, exc_val, exc_tb)


def _set_attributes(span: Any, attributes: Mapping[str, Any]) -> None:
    for key, value in attributes.items():
        if value is None:
            continue
        try:
            span.set_attribute(key, value)
        except (TypeError, ValueError):
            logger.debug("Unable to set OTel attribute %s=%r", key, value, exc_info=True)



class StartedSpan:
    """Explicitly-started span with an active context."""

    def __init__(self, name: str, attributes: Mapping[str, Any]) -> None:
        self._span = tracer.start_span(name)
        self._scope = trace.use_span(self._span, end_on_exit=False)
        self._scope.__enter__()
        _set_attributes(self._span, attributes)

    @property
    def span(self):
        return self._span

    def end(self) -> None:
        try:
            self._span.end()
        finally:
            self._scope.__exit__(None, None, None)


def start_span(name: str, **attributes: Any) -> StartedSpan:
    return StartedSpan(name, attributes)


def end_span(span: StartedSpan | Any) -> None:
    if isinstance(span, StartedSpan):
        span.end()
    elif span is not None and hasattr(span, "end"):
        span.end()


def create_span(name: str, **attributes: Any) -> SpanContextManager:
    """Create a current span and attach non-None attributes."""
    return SpanContextManager(name, attributes)


def set_span_attributes(**attributes: Any) -> None:
    """Set attributes on the currently active span."""
    span = trace.get_current_span()
    if span.get_span_context().is_valid:
        _set_attributes(span, attributes)


def mark_span_error(error: BaseException, **attributes: Any) -> None:
    """Mark the current span as failed without swallowing the exception."""
    span = trace.get_current_span()
    if not span.get_span_context().is_valid:
        return
    _set_attributes(span, attributes)
    span.record_exception(error)
    span.set_status(trace.StatusCode.ERROR, str(error))
    span.set_attribute("outcome", "error")


def increment_request_count() -> int:
    global _request_count
    with _request_count_lock:
        _request_count += 1
        return _request_count


def get_request_count() -> int:
    with _request_count_lock:
        return _request_count


def get_trace_id() -> str | None:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


def get_span_id() -> str | None:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return format(context.span_id, "016x")
