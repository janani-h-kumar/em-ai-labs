# Observability Setup

This project uses structured JSON logs plus OpenTelemetry spans. The local
development path is intentionally local-only: spans can be written to a JSONL
file and inspected without sending data to a hosted service.

## Current Span Flow

A normal request produces a trace shaped like this:

```text
agent_manager.handle
  orchestrator.run
    planner.create_plan
      llm.chat_completion
    executor.execute_task
      agent.handle
        tool.execute
          tool.api_request
        llm.chat_completion
```

Some spans only appear when the code path uses them. For example,
`planner.create_plan` only contains an LLM call when the planner heuristic
decides the request is compound enough to ask the local model for a plan.

## Span Attributes

`agent_manager.handle` captures request-level metadata:

```text
request_id
session_id
request_count
message_length
request_latency_ms
```

`orchestrator.run` captures orchestration and memory timing:

```text
session_id
goal
memory_latency_ms
orchestrator_latency_ms
```

`planner.create_plan` captures planning behavior:

```text
session_id
goal
planner.heuristic_skip
planner_latency_ms
```

`executor.execute_task` captures task routing and status:

```text
task.id
task.description
session.id
correlation.id
agent.name
duration_ms
task.status
```

`agent.handle` captures the selected agent call:

```text
agent_name
task_id
session_id
agent_latency_ms
```

`tool.execute` captures tool execution:

```text
tool_name
args
kwargs
tool_latency_ms
```

`tool.api_request` captures outbound network/API calls made by tools:

```text
tool_name
api_service
http_method
url
http.status_code
api_latency_ms
```

`llm.chat_completion` captures local LLM latency and token usage:

```text
llm_provider
model_name
message_count
max_tokens
has_system_prompt
llm_latency_ms
prompt_tokens
completion_tokens
total_tokens
```

The LLM span does not store prompt text or model responses. It records metadata
needed for latency and cost-style analysis.

## Local JSONL Export

For local development, use the file exporter:

```powershell
$env:OTEL_TRACES_EXPORTER = "file"
$env:OTEL_TRACE_FILE = "logs/traces.jsonl"
```

Then run the app normally. Completed spans are appended to `logs/traces.jsonl`,
one JSON object per line.

The same values are included in `.env.dev` and `.env.example`. The tracing
module loads `.env` and the active `.env.<APP_ENV>` file before choosing an
exporter, so `.env.dev` is enough for the normal local runtime path. Shell
environment variables still win when you want to override the file values.

## Viewing The File Locally

Basic PowerShell inspection:

```powershell
Get-Content logs\traces.jsonl
```

Pretty print when `jq` is installed:

```powershell
Get-Content logs\traces.jsonl | jq .
```

Show only LLM spans:

```powershell
Get-Content logs\traces.jsonl | jq 'select(.name == "llm.chat_completion")'
```

Show token and latency fields for LLM spans:

```powershell
Get-Content logs\traces.jsonl |
  jq 'select(.name == "llm.chat_completion") |
  {trace_id, duration_ms, model: .attributes.model_name, prompt_tokens: .attributes.prompt_tokens, completion_tokens: .attributes.completion_tokens, total_tokens: .attributes.total_tokens}'
```

## Future OTLP Export

When you are ready to send traces to a collector such as Jaeger or an
OpenTelemetry Collector, switch the exporter mode:

```powershell
$env:OTEL_TRACES_EXPORTER = "otlp"
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
```

The instrumentation calls do not need to change. Only the exporter mode changes
from `file` to `otlp`.

## Privacy Notes

The local JSONL exporter writes span names, IDs, timings, status, events, and
attributes. Current LLM spans intentionally avoid prompt and completion bodies.
Some existing orchestration spans include the request goal or task description;
avoid sharing trace files externally if those may contain sensitive user input.
