"""
OpenTelemetry tracing setup for em-ai-labs.

[Pillar 3] Provides one tracer for the execution path. Falls back to a NoOp
tracer with zero overhead and zero configuration required — tracing is
entirely opt-in via an environment variable, so this module is always safe
to import regardless of whether OTel infrastructure exists in a given
environment (local dev, CI, production).

To enable real export to Jaeger locally:

    docker run -d --name jaeger \
        -p 16686:16686 \
        -p 4317:4317 \
        jaegertracing/all-in-one:latest

Then set in configs/.env or .env.dev:

    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

Leave it unset (the default) to use the NoOp tracer — spans are created and
discarded with no network calls and no measurable overhead.

Why this exists: structured logging (logging_utils.py) tells you *what*
happened on a request, including a correlation_id that ties every log line
to one request. It does not tell you *how long each step took* or *where
the time went* across a multi-step orchestration. Spans answer that — e.g.
whether a 30-second weather request spent its time in the tool call or the
LLM call (it's almost always the LLM call, but now you can prove it instead
of inferring it from log timestamps).
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)

_SERVICE_NAME = "em-ai-labs"


def setup_tracing(service_name: str = _SERVICE_NAME) -> trace.Tracer:
    """
    Initialise OpenTelemetry tracing.

    Returns a real tracer wired to export spans via OTLP/gRPC when
    OTEL_EXPORTER_OTLP_ENDPOINT is set in the environment. Otherwise returns
    the OTel NoOp tracer — span creation, attribute setting, and
    start_as_current_span all work identically, they just produce nothing.
    Callers never need to branch on whether tracing is "really" enabled.

    Args:
        service_name: Reported as service.name on every exported span.

    Returns:
        A trace.Tracer — always safe to call span methods on.
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
            "OTEL_EXPORTER_OTLP_ENDPOINT is set but the OTLP gRPC exporter "
            "is not installed — falling back to NoOp tracer. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
        )
    except Exception:
        logger.exception(
            "Failed to initialise OTel exporter for endpoint=%s — falling back to NoOp tracer",
            endpoint,
        )

    return trace.get_tracer(service_name)


# Module-level tracer — import this wherever a span is needed:
#   from src.utils.tracing import tracer
tracer = setup_tracing()
