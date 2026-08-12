"""Lightweight OpenTelemetry metrics for agent cost/usage observability.

This module creates metrics only. It does not provide a dashboard or retain a
second application-side metrics store. Export is controlled by the standard
OTEL_METRICS_EXPORTER / OTEL_EXPORTER_OTLP_ENDPOINT environment variables.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_METER_NAME = "em-ai-labs.observability"
_provider_configured = False


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    app_env = (os.getenv("APP_ENV") or "dev").lower()
    load_dotenv(repo_root / f".env.{app_env}", override=False)


def setup_metrics(service_name: str = "em-ai-labs") -> metrics.Meter:
    """Configure OTEL metrics and return the application meter.

    With no exporter configured, the OpenTelemetry API's no-op meter is used.
    With OTEL_METRICS_EXPORTER=otlp, metrics are exported through OTLP/gRPC.
    """
    global _provider_configured
    _load_env()

    if not _provider_configured:
        exporter_mode = (os.getenv("OTEL_METRICS_EXPORTER") or "none").strip().lower()
        if exporter_mode in {"otlp", "otlp_proto_grpc"}:
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                        OTLPMetricExporter,
                    )
                    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

                    reader = PeriodicExportingMetricReader(
                        OTLPMetricExporter(endpoint=endpoint, insecure=True)
                    )
                    provider = MeterProvider(
                        resource=Resource.create({"service.name": service_name}),
                        metric_readers=[reader],
                    )
                    metrics.set_meter_provider(provider)
                    _provider_configured = True
                    logger.info("OpenTelemetry metrics enabled - exporting OTLP to %s", endpoint)
                except ImportError:
                    logger.warning(
                        "OTEL metrics exporter is not installed; using the default no-op meter"
                    )
                except Exception:
                    logger.exception("Failed to initialise OpenTelemetry metrics")
            else:
                logger.warning(
                    "OTEL_METRICS_EXPORTER=otlp but OTEL_EXPORTER_OTLP_ENDPOINT is unset"
                )

        # Mark as configured even when no exporter is requested so this module
        # does not repeatedly attempt provider registration.
        if not _provider_configured:
            _provider_configured = True

    return metrics.get_meter(_METER_NAME)


meter = setup_metrics()

agent_run_duration = meter.create_histogram(
    "agent.run.duration",
    unit="ms",
    description="Agent run duration in milliseconds",
)
agent_llm_input_tokens = meter.create_histogram(
    "agent.llm.input_tokens",
    unit="{token}",
    description="LLM input token usage",
)
agent_llm_output_tokens = meter.create_histogram(
    "agent.llm.output_tokens",
    unit="{token}",
    description="LLM output token usage",
)
agent_llm_total_tokens = meter.create_histogram(
    "agent.llm.total_tokens",
    unit="{token}",
    description="Total LLM token usage",
)
agent_tool_duration = meter.create_histogram(
    "agent.tool.duration",
    unit="ms",
    description="Tool execution duration in milliseconds",
)
agent_tool_response_size = meter.create_histogram(
    "agent.tool.response_size_bytes",
    unit="By",
    description="Tool response size in bytes",
)
agent_run_tool_calls = meter.create_histogram(
    "agent.run.tool_calls",
    unit="{call}",
    description="Number of tool calls in an agent run",
)
agent_run_retry_count = meter.create_histogram(
    "agent.run.retry_count",
    unit="{retry}",
    description="Retry count observed during an agent run",
)


def _attributes(attributes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep metric labels to the documented low-cardinality dimensions."""
    allowed = {"agent.name", "provider", "model", "tool.name", "outcome", "environment"}
    source = dict(attributes or {})
    source.setdefault("environment", os.getenv("APP_ENV", "dev"))
    return {key: value for key, value in source.items() if key in allowed and value is not None}


def record_agent_run(
    duration_ms: float,
    *,
    tool_calls: int = 0,
    retry_count: int = 0,
    attributes: dict[str, Any] | None = None,
) -> None:
    labels = _attributes(attributes)
    agent_run_duration.record(duration_ms, labels)
    agent_run_tool_calls.record(tool_calls, labels)
    agent_run_retry_count.record(retry_count, labels)


def record_llm_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    attributes: dict[str, Any] | None = None,
) -> None:
    labels = _attributes(attributes)
    agent_llm_input_tokens.record(input_tokens, labels)
    agent_llm_output_tokens.record(output_tokens, labels)
    agent_llm_total_tokens.record(total_tokens, labels)


def record_tool(
    *,
    duration_ms: float,
    response_size_bytes: int = 0,
    attributes: dict[str, Any] | None = None,
) -> None:
    labels = _attributes(attributes)
    agent_tool_duration.record(duration_ms, labels)
    agent_tool_response_size.record(response_size_bytes, labels)
