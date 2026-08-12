# P0 Observability Task List

This task list defines the concrete repo changes required to implement cost and token observability for `em-ai-labs` without adding a custom dashboard. It focuses on telemetry instrumentation, OpenTelemetry compatibility, and documentation updates.

## Objective

Emit structured telemetry for:

- agent runs
- LLM calls
- tool calls
- API requests
- retry behavior
- token usage
- latency
- context size

Do not introduce an in-repo dashboard UI. The backend target is OpenTelemetry + Grafana/Tempo/Prometheus.

---

## Task 1: Standardize span schema and attributes

### Files

- `src/observability/tracing.py`
- `src/observability/trace_summary.py`

### Work

- Define canonical span names:
  - `agent.run`
  - `llm.call`
  - `tool.call`
  - `tool.api_request`
- Confirm the span attribute contract includes:
  - `agent.name`
  - `agent.version`
  - `execution.id`
  - `session.id`
  - `iteration`
  - `outcome`
  - `duration_ms`
  - `tool_calls`
  - `retry_count`
  - `context_size_tokens`
  - `provider`
  - `model`
  - `input_tokens`
  - `output_tokens`
  - `total_tokens`
  - `response_size_bytes`
  - `api_service`
  - `api_latency_ms`
  - `http.status_code`

- Update `trace_summary.py` to recognize the new span names and attributes for future summaries and tests.

---

## Task 2: Instrument runtime telemetry

### Files

- `src/runtimes/langchain_runtime.py`
- `src/runtimes/base_runtime.py`

### Work

- Ensure runtime telemetry includes:
  - `input_tokens`
  - `output_tokens`
  - `total_tokens`
  - `latency_ms`
  - `model`
  - `context_size_tokens`
- Ensure the runtime emits or propagates the `agent.run` span at the start of each execution.
- Confirm `BaseRuntime` documents telemetry expectations and exposes `get_telemetry()`.

---

## Task 3: Instrument tool execution

### Files

- `src/tools/base_tool.py`
- `src/tools/weather_tool.py`

### Work

- Record a `tool.call` span around every `BaseTool` execution.
- Add `response_size_bytes` to the tool span.
- Add `retry_count` and `outcome` to `tool.call`.
- In `src/tools/weather_tool.py`, ensure outbound API call spans are emitted as `tool.api_request` with:
  - `tool.name`
  - `api_service`
  - `http.status_code`
  - `api_latency_ms`
  - `response_size_bytes` when available

---

## Task 4: Normalize provider / LLM instrumentation

### Files

- `src/providers/ollama_provider.py`
- `src/providers/claude_provider.py`
- `src/providers/base_provider.py`

### Work

- Ensure both providers emit `llm.call` spans with consistent metadata.
- Confirm the providers set `prompt_tokens`, `completion_tokens`, and `total_tokens` as span attributes.
- Add `provider` and `model` attributes to the LLM span.
- Avoid storing prompt/completion text in spans; only metadata.
- If token counts are available only in provider response, normalize them into the same attribute names in both providers.

---

## Task 5: Instrument retry behavior

### Files

- `src/middleware/retry.py`

### Work

- Add retry telemetry to the active span or a child span when retries occur.
- Emit:
  - `retry_count`
  - `retry_reason`
  - `retry_latency_ms`
- Ensure retry metadata is available on `tool.call` or `agent.run` spans for aggregate analysis.

---

## Task 6: Add metrics export support

### Files

- `src/observability/tracing.py`
- `src/observability/metrics.py` (new)

### Work

- Add a dedicated metrics helper or module for OpenTelemetry metrics if one does not exist.
- Recommend adding metrics for:
  - `agent.run.duration`
  - `agent.llm.input_tokens`
  - `agent.llm.output_tokens`
  - `agent.llm.total_tokens`
  - `agent.tool.duration`
  - `agent.tool.response_size_bytes`
  - `agent.run.tool_calls`
  - `agent.run.retry_count`
- Keep labels low-cardinality:
  - `agent.name`
  - `provider`
  - `model`
  - `tool.name`
  - `outcome`
  - `environment`
- Do not use high-cardinality IDs like `session_id` or `request_id` as metric labels.

---

## Task 7: Add or update documentation

### Files

- `docs/observability.md`
- `README.md`
- `PLAN.md`

### Work

- Document the observability pattern and the fact that the repo emits telemetry only.
- Add a new section describing the span schema and metric names.
- Explain that Grafana/Tempo/Prometheus is the intended dashboard/backend.
- Clarify that cost is represented by token usage and latency, not by dollar price at P0.

---

## Task 8: Add tests

### Files

- `tests/unit/test_observability_tracing.py`
- `tests/unit/test_observability_metrics.py`
- `tests/integration/test_observability_integration.py`

### Work

- Add unit tests for trace/span attribute naming and generation.
- Add unit tests for metric helper behavior if a new metrics module is created.
- Add integration tests that verify `logs/traces.jsonl` or trace export includes token counts, span names, and tool call metadata.
- Ensure test coverage for `llm.call`, `tool.call`, and `tool.api_request` attributes.

---

## Recommended new file(s)

- `src/observability/metrics.py` — helper functions for OpenTelemetry metric creation and export
- `src/observability/run_metrics.py` — optional aggregator for per-run telemetry in testable form

These files should remain lightweight and focused on instrumentation, not visualization.

---

## Suggested implementation order

1. `src/observability/tracing.py`
2. `src/runtimes/langchain_runtime.py`
3. `src/tools/base_tool.py`
4. `src/providers/ollama_provider.py` and `src/providers/claude_provider.py`
5. `src/middleware/retry.py`
6. `src/observability/metrics.py` (new)
7. `docs/observability.md`
8. `tests/unit/test_observability_tracing.py`
9. `tests/integration/test_observability_integration.py`
