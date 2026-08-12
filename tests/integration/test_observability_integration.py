import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from src.observability import tracing


def test_canonical_trace_export_contains_usage_and_tool_metadata(tmp_path):
    output = tmp_path / "traces.jsonl"
    exporter = tracing.JsonlSpanExporter(str(output))
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    original_tracer = tracing.tracer
    tracing.tracer = provider.get_tracer("integration-test")

    try:
        with tracing.create_span(
            "agent.run",
            **{
                "agent.name": "WeatherAgent",
                "agent.version": "1",
                "execution.id": "exec-1",
                "session.id": "session-1",
                "context_size_tokens": 20,
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
                "outcome": "success",
            },
        ):
            with tracing.create_span(
                "llm.call",
                provider="ollama",
                model="phi3",
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                outcome="success",
            ):
                pass

            with tracing.create_span(
                "tool.call",
                **{"tool.name": "weather_tool"},
                response_size_bytes=128,
                retry_count=1,
                outcome="success",
            ):
                with tracing.create_span(
                    "tool.api_request",
                    **{
                        "tool.name": "weather_tool",
                        "api_service": "openweathermap",
                        "http.status_code": 200,
                        "api_latency_ms": 42.0,
                        "response_size_bytes": 128,
                    },
                    outcome="success",
                ):
                    pass
    finally:
        tracing.tracer = original_tracer
        provider.shutdown()

    spans = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    names = {span["name"] for span in spans}
    assert {"agent.run", "llm.call", "tool.call", "tool.api_request"} <= names

    llm = next(span for span in spans if span["name"] == "llm.call")
    assert llm["attributes"]["input_tokens"] == 20
    assert llm["attributes"]["output_tokens"] == 10
    assert llm["attributes"]["total_tokens"] == 30

    api = next(span for span in spans if span["name"] == "tool.api_request")
    assert api["attributes"]["api_service"] == "openweathermap"
    assert api["attributes"]["http.status_code"] == 200
    assert api["attributes"]["response_size_bytes"] == 128
