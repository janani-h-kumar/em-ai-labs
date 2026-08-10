# LangGraph Integration Plan

## Goal

Make LangGraph an optional orchestration runtime for em-ai-labs so each
conversation can be debugged as a timeline of durable state transitions:
memory retrieval, planning, routing, task execution, reasoning, synthesis,
guardrails, and persistence.

The first usable milestone is not to replace the existing ReACT loop outright.
It is to add a graph-backed execution path inside `Orchestrator` with a safe
fallback to the current ReACT implementation.

## Current Status

### Completed

- [x] Added `langgraph==0.2.76` and `langgraph-checkpoint==2.0.26` to
  `pyproject.toml`.
- [x] Added initial `src/orchestration/graph_builder.py`.
- [x] Introduced `AgentState` as the typed graph state shape.
- [x] Added planner and executor graph nodes.
- [x] Added a checkpointer construction path.
- [x] Added regression coverage in `tests/unit/test_graph_builder.py`.
- [x] Updated `tests/conftest.py` so real LangChain/LangGraph packages are not
  shadowed when installed.

### Working

- LangGraph packages are installed and importable in the workspace.
- The graph builder module imports successfully.
- Targeted graph builder tests pass when run without the repository-wide
  coverage gate.

### Gaps

- Sqlite checkpointing is wired as the production target in code/config, but the
  current venv still needs `langgraph-checkpoint-sqlite` synced before sqlite
  mode can run locally.
- The first graph runtime keeps synthesis and output guardrail centralized in
  `Orchestrator`; moving them into graph nodes remains a later parity step.
- The first graph runtime uses direct planner -> executor execution. A
  graph-native iterative reasoning loop remains a later parity step.
- There is no user-facing conversation timeline accessor yet.

## Decisions

- Enable LangGraph through `config.yaml`; no environment-variable override is
  needed for this milestone.
- Default graph failure behavior during development is to surface the graph
  error. ReACT fallback exists but must be explicitly enabled.
- Result previews are included in timeline events by default, with a config path
  available to opt out later.
- Timeline data should be both human-readable and machine-readable, with human
  debugging as the first priority.
- Timeline and checkpoint data should persist until an explicit cleanup control
  is added later.
- The first runtime implementation should use direct
  `memory_context -> planner -> executor`, while preserving state shape and node
  naming for a later reasoning/observe loop.

## Design Principles

- Preserve current behavior by default until the graph path has parity.
- Keep all request state in `ExecutionContext`; agents stay stateless.
- Treat LangGraph checkpointing as orchestration state, not as a replacement for
  user-facing conversation memory.
- Keep chat history in the existing `BaseMemory` abstraction.
- Emit timeline events from orchestration boundaries rather than from agent
  internals.
- Store enough state to debug execution order and failures, but do not persist
  raw prompts, raw completions, secrets, or tool credentials.
- Make rollback easy: one config flag should return the runtime to the existing
  ReACT loop.

## Target Runtime Shape

```text
ApplicationService.handle
  Orchestrator.run
    load conversation memory
    build ExecutionContext
    choose runtime path
      langgraph path
        graph.start
        memory_context node
        planner node
        optional reasoning node
        executor node(s)
        synthesis node
        output_guardrail node
        persist_exchange node
        graph.end
      fallback path
        existing ReACTLoop.run
    return final response
```

The graph path should return the same final response contract as the legacy
path: `Orchestrator.run(goal, session_id) -> str`.

## Proposed AgentState

`AgentState` should evolve from the current minimal adapter shape into a
debuggable orchestration envelope.

```python
class AgentState(TypedDict, total=False):
    session_id: str
    goal: str
    context: ExecutionContext
    memory_messages: list[dict[str, Any]]
    plan: list[TaskState]
    ready_tasks: list[str]
    results: list[TaskResultState]
    final_response: str
    error: ErrorState | None
    timeline: list[TimelineEvent]
    metadata: dict[str, Any]
```

Recommended nested state records:

```python
class TimelineEvent(TypedDict):
    event_id: str
    session_id: str
    thread_id: str
    node: str
    event_type: str
    status: str
    timestamp: str
    duration_ms: float | None
    trace_id: str | None
    span_id: str | None
    attributes: dict[str, Any]

class TaskState(TypedDict):
    id: str
    description: str
    assigned_agent: str | None
    dependencies: list[str]
    parallelizable: bool
    status: str

class TaskResultState(TypedDict):
    task_id: str
    agent_name: str | None
    status: str
    result_preview: str
    result: Any

class ErrorState(TypedDict):
    node: str
    type: str
    message: str
    recoverable: bool
```

Notes:

- `thread_id` should map to LangGraph's checkpoint thread id. Use
  `session_id` initially unless a later UI needs finer-grained run IDs.
- `result_preview` supports quick timeline inspection without forcing a UI or
  logs to render large payloads.
- `timeline` is the user-facing debugging layer; LangGraph checkpoints are the
  durable replay layer.

## Configuration Plan

Add orchestration config under `runtime`:

```yaml
runtime:
  orchestration: "react"        # "react" or "langgraph"
  langgraph:
    enabled: false
    fallback_to_react: false
    checkpoint:
      enabled: false
      backend: "memory"         # "memory" first, "sqlite" next
      db_path: "./data/langgraph_checkpoints.sqlite"
    timeline:
      enabled: true
      include_result_previews: true
      max_preview_chars: 500
```

Acceptance criteria:

- Missing `runtime.langgraph` config keeps current behavior.
- `runtime.orchestration: "react"` always uses the existing ReACT path.
- `runtime.orchestration: "langgraph"` uses graph execution when available.
- If graph execution fails and `fallback_to_react` is true, the orchestrator logs
  the failure, adds a timeline event, and returns the ReACT result.
- If graph execution fails and fallback is false, the orchestrator raises the
  original error through the existing application error path.

## Implementation Plan

### Phase 1: Correct the Graph Adapter

- [x] Make planner and executor nodes async.
- [x] Compile the graph before invocation.
- [x] Return a compiled graph app from `GraphBuilder`, or expose explicit
  `build_graph()` and `compile()` methods.
- [x] Pass `provider` through `AgentState` or attach it to `ExecutionContext` in
  a typed way. The current `getattr(context, "provider", None)` path is fragile
  because `ExecutionContext` does not define `provider`.
- [x] Preserve full `Task` fields when converting tasks into state.
- [x] Convert state task records back into real `Task` objects without dynamic
  shim classes.
- [x] Add graph-level error capture so failed nodes populate `state["error"]`
  before fallback or re-raise.

Recommended first shape:

```text
GraphBuilder.compile(checkpointer=None) -> CompiledStateGraph
GraphBuilder.ainvoke(initial_state, config=None) -> AgentState
```

Tests:

- [x] Graph compiles successfully.
- [x] Compiled graph runs through async planner and executor nodes.
- [x] Provider is available to planner without dynamic attributes.
- [x] Task dependencies and statuses survive state serialization.

### Phase 2: Add Orchestrator Runtime Selection

- [x] Add an orchestration mode resolver to `Orchestrator`.
- [x] Instantiate `GraphBuilder(planner=self.planner, executor=self.executor)`.
- [x] Add `_run_react(...)` helper containing the existing ReACT behavior.
- [x] Add `_run_langgraph(...)` helper that builds initial state, invokes the
  compiled graph, and returns `state["results"]` or `state["final_response"]`.
- [x] Keep synthesis and output guardrail behavior equivalent across both paths.
- [x] Store the final user/assistant exchange exactly once, regardless of path.
- [x] Add fallback handling around only the graph execution boundary.

Suggested orchestrator flow:

```text
history = memory.get_history(session_id)
context = ExecutionContext(...)

if orchestration_mode == "langgraph":
    try:
        results_or_response = await _run_langgraph(goal, session_id, context)
    except Exception:
        if fallback_to_react:
            results = await _run_react(goal, context)
        else:
            raise
else:
    results = await _run_react(goal, context)

final_response = synthesize/validate
memory.add_user_message/add_ai_message
return final_response
```

Tests:

- [x] Default config still calls `ReACTLoop.run`.
- [x] LangGraph config calls the compiled graph.
- [x] Graph failure falls back to ReACT when enabled.
- [x] Graph failure does not fall back when disabled.
- [x] Memory writes happen once on success.
- [ ] Output guardrail still blocks empty graph responses.

### Phase 3: Timeline Events

- [ ] Add a small timeline utility, for example
  `src/observability/timeline.py`.
- [ ] Define `TimelineEvent` helpers for `start`, `success`, `failure`, and
  `checkpoint`.
- [ ] Record events at these boundaries:
  - `orchestrator.start`
  - `memory.loaded`
  - `graph.start`
  - `planner.start`
  - `planner.completed`
  - `executor.task.started`
  - `executor.task.completed`
  - `executor.task.failed`
  - `synthesis.completed`
  - `output_guardrail.completed`
  - `memory.persisted`
  - `graph.fallback_to_react`
  - `orchestrator.completed`
- [ ] Attach `trace_id` and `span_id` from `src.observability.tracing`.
- [ ] Store timeline events in `ExecutionContext.metadata["timeline"]` and mirror
  them into `AgentState["timeline"]` during graph execution.
- [ ] Add structured log events with `session_id`, `node`, `event_type`,
  `status`, and `duration_ms`.

Acceptance criteria:

- A single conversation can be reconstructed from timeline events without
  reading free-form logs.
- Every timeline event has a stable event type and timestamp.
- Timeline events include enough routing/task metadata to explain which agent
  handled each task.
- Timeline records avoid full prompt and completion bodies by default.

### Phase 4: Persistence and Replay

- [ ] Keep `MemorySaver` as the test/default checkpointer.
- [ ] Add sqlite checkpointer support behind config.
- [ ] Store checkpoints under a repo-local ignored data path such as
  `data/langgraph_checkpoints.sqlite`.
- [ ] Use LangGraph config with `configurable.thread_id = session_id`.
- [ ] Add a small debug accessor that can fetch timeline/checkpoint summaries by
  `session_id`.
- [ ] Document how to inspect a conversation locally.

Tests:

- [ ] Memory checkpointer records state across graph steps.
- [ ] Sqlite checkpointer can reload a prior session state.
- [ ] Checkpoint thread IDs are derived from session IDs.
- [ ] Clearing conversation memory does not accidentally delete graph
  checkpoints unless explicitly requested.

### Phase 5: Observability Integration

- [ ] Wrap each graph node in an OTel span.
- [ ] Use consistent span names:
  - `langgraph.node.memory_context`
  - `langgraph.node.planner`
  - `langgraph.node.executor`
  - `langgraph.node.synthesis`
  - `langgraph.node.output_guardrail`
- [ ] Add attributes:
  - `session_id`
  - `graph.thread_id`
  - `graph.node`
  - `graph.step`
  - `task.id`
  - `task.status`
  - `agent.name`
  - `fallback.used`
- [ ] Add timeline event IDs as span attributes so JSONL traces and timeline
  records can be joined.
- [ ] Update `docs/observability.md` with the LangGraph span flow.

Tests:

- [ ] File trace exporter emits LangGraph node spans when graph mode is enabled.
- [ ] Timeline events include trace/span IDs when tracing is active.
- [ ] Existing ReACT tracing tests continue to pass.

### Phase 6: Parity and Gradual Cutover

- [ ] Compare graph path vs ReACT path for simple single-task prompts.
- [ ] Compare graph path vs ReACT path for multi-step prompts.
- [ ] Add an integration smoke test through `ApplicationService.handle`.
- [ ] Run both modes in local CI.
- [ ] Keep ReACT as the default until graph mode passes parity tests.
- [ ] Flip default only after checkpointing, timeline inspection, and fallback
  behavior are verified.

## Timeline Debug Output

The desired local debug view should be able to answer:

- What message started this conversation?
- What memory was loaded?
- Did the request use ReACT or LangGraph?
- Which graph nodes ran, in what order, and how long did each take?
- What plan was produced?
- Which agent handled each task?
- What did each task return?
- Did any guardrail fire?
- Did graph execution fall back to ReACT?
- What final response was persisted?

Recommended first CLI/debug representation:

```json
{
  "session_id": "abc123",
  "runtime": "langgraph",
  "final_status": "completed",
  "events": [
    {
      "node": "orchestrator",
      "event_type": "orchestrator.start",
      "status": "started",
      "timestamp": "2026-08-06T12:00:00Z"
    },
    {
      "node": "planner",
      "event_type": "planner.completed",
      "status": "completed",
      "duration_ms": 12.4,
      "attributes": {"task_count": 1}
    }
  ]
}
```

## Suggested File Changes

- `src/orchestration/graph_builder.py`
  - Compile graph before use.
  - Convert nodes to async.
  - Preserve full task state.
  - Add timeline event hooks.

- `src/orchestration/orchestrator.py`
  - Add runtime selection.
  - Add graph execution path.
  - Add graph-to-ReACT fallback.
  - Keep memory persistence and output guardrail centralized.

- `src/orchestration/models.py`
  - Optionally add typed serializable task/timeline records, or keep them in a
    new graph-specific model module if that keeps the core model cleaner.

- `src/observability/timeline.py`
  - New helper module for timeline event creation and preview redaction.

- `src/utils/config_loader.py`
  - No major change required; dot-notation config lookup already supports the
    proposed nested settings.

- `configs/config.yaml.example`
  - Add `runtime.langgraph` defaults.

- `docs/observability.md`
  - Document graph spans and timeline inspection.

- `tests/unit/test_graph_builder.py`
  - Update to assert compiled async graph behavior.

- `tests/unit/test_orchestrator_langgraph.py`
  - Add optional graph path and fallback tests.

- `tests/unit/test_timeline.py`
  - Add event shape, preview, and trace correlation tests.

- `tests/integration/test_langgraph_runtime.py`
  - Add end-to-end graph-mode smoke coverage.

## Open Questions

These are the only items that need product/runtime decisions before the full
implementation:

- Should LangGraph mode be enabled through `runtime.orchestration:
  "langgraph"` only, or should there also be a separate environment variable
  override for local debugging?
- Should timeline debug data be exposed only through logs/files at first, or do
  you want an application method such as `get_timeline(session_id)`?
- Should sqlite checkpoints be considered local-dev only for now, or do they
  need to be production-ready in this milestone?
- What data retention policy should timeline and checkpoint files follow?

## Recommended Next Milestone

Implement Phases 1 and 2 together:

1. Fix graph compilation and async invocation.
2. Wire LangGraph into `Orchestrator` behind config.
3. Preserve ReACT fallback.
4. Add tests proving both runtime paths return the same response shape.

Then implement Phase 3 immediately after, because the main reason to adopt
LangGraph here is conversation timeline debugging.
