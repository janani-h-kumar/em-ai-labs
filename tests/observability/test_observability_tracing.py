from src.observability import tracing


def test_canonical_span_names():
    assert tracing.CANONICAL_SPAN_NAMES == {
        "agent.run",
        "llm.call",
        "tool.call",
        "tool.api_request",
    }


def test_canonical_attributes_include_cost_and_latency_fields():
    expected = {
        "agent.name",
        "agent.version",
        "execution.id",
        "session.id",
        "outcome",
        "duration_ms",
        "retry_count",
        "context_size_tokens",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "response_size_bytes",
        "api_service",
        "api_latency_ms",
        "http.status_code",
    }
    assert expected <= tracing.CANONICAL_ATTRIBUTES


def test_jsonl_exporter_writes_span(tmp_path):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    output = tmp_path / "traces.jsonl"
    exporter = tracing.JsonlSpanExporter(str(output))
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("test")

    with test_tracer.start_as_current_span("llm.call") as span:
        span.set_attribute("provider", "ollama")
        span.set_attribute("model", "test-model")
        span.set_attribute("input_tokens", 10)
        span.set_attribute("output_tokens", 5)
        span.set_attribute("total_tokens", 15)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"name": "llm.call"' in lines[0]
    assert '"total_tokens": 15' in lines[0]
