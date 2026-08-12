# Observability

## P0 architecture

`em-ai-labs` uses OpenTelemetry for application tracing and sends traces over
OTLP to Jaeger during local development:

```text
Agent Framework
      |
      | OpenTelemetry SDK
      v
OTLP exporter
      |
      v
Jaeger all-in-one
      |
      v
Jaeger UI
```

There is deliberately **no custom dashboard, database, Prometheus, Loki, or
trace-file exporter** in the application.

Start local Jaeger with:

```powershell
docker compose -f docker-compose.observability.yml up -d
```

Open Jaeger at `http://localhost:16686`.

The application defaults to:

```text
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

For tests or environments where export should be disabled:

```powershell
$env:OTEL_TRACES_EXPORTER = "none"
```

## Span hierarchy

The primary execution trace is structured as:

```text
request
  |
  +-- orchestrator.run
       |
       +-- planner.create_plan
       |
       +-- executor.execute_task
       |     |
       |     +-- agent.run
       |           |
       |           +-- llm.call
       |           +-- tool.call
       |                 |
       |                 +-- tool.api_request
       |
       +-- output guardrail / completion
```

The important canonical spans are:

- `agent.run`
- `llm.call`
- `tool.call`
- `tool.api_request`

The application also retains useful orchestration spans such as
`orchestrator.run`, `planner.create_plan`, and `executor.execute_task`.

## Common attributes

### Agent

- `agent.name`
- `agent.version`
- `execution.id`
- `session.id`
- `iteration`
- `outcome`
- `duration_ms`

### LLM

- `provider`
- `model`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `context_size_tokens`
- `latency_ms`
- `response_size_bytes`
- `outcome`

Provider-specific prompt/completion aliases may also be present for backwards
compatibility, but `input_tokens` and `output_tokens` are the canonical names.
Prompt or completion text is never stored in spans.

### Tool

- `tool.name`
- `tool_name`
- `duration_ms`
- `response_size_bytes`
- `outcome`
- `error.type`

### API request

- `tool.name` / `tool_name`
- `api_service`
- `http.status_code`
- `api_latency_ms`
- `response_size_bytes`
- `outcome`
- `error.type`

## External API health semantics

Tool construction must not call an external service. A tool being registered
means its configuration and dependencies can be constructed; it does **not**
mean the remote API is healthy.

For example, a weather API response of HTTP 401 is recorded as:

```text
weather_tool
  outcome = error
  http.status_code = 401
  error.type = WeatherAuthenticationError
  api_latency_ms = ...
```

The API request span is the source of truth for remote-service health. This
prevents misleading messages such as `API reachable (401)` followed by
`client initialized successfully`.

## Dependency failures

Agent constructor dependencies are required to resolve before an agent is
created. `AgentFactory` fails fast with `AgentDependencyError` when a required
dependency is missing instead of allowing Python to raise a later
`TypeError` from the constructor.

## Logging correlation

Structured logs use the active OpenTelemetry context. During a normal request,
`trace_id` and `span_id` therefore point directly to the corresponding Jaeger
trace/span. No second application-level trace ID is created.

`correlation_id` remains as request/application metadata for compatibility, but
OpenTelemetry is the authoritative trace context.

## P0 scope

P0 is intentionally trace-first. Token usage and latency are recorded on LLM
spans so cost analysis can be performed from traces. A separate metrics backend
can be added later without changing the trace model.
