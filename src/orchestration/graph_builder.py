"""LangGraph-based orchestration builder for em-ai-labs."""

from __future__ import annotations

import logging
from typing import Any, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from src.observability.timeline import (
    TimelineTimer,
    append_timeline_event,
    preview_value,
)
from src.orchestration.executor import Executor
from src.orchestration.models import ExecutionContext, Task, TaskStatus
from src.orchestration.planner import Planner

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    """State carried through the LangGraph workflow."""

    session_id: str
    goal: str
    context: ExecutionContext
    provider: Any
    plan: list[dict]
    results: list[object]
    final_response: str
    timeline: list[dict]
    metadata: dict[str, Any]
    approved: bool
    error: dict[str, Any] | str | None


class HumanApprovalRequiredError(Exception):
    """Raised when an opt-in human approval checkpoint is reached."""


class GraphBuilder:
    """Build a LangGraph workflow around the existing planner/executor components."""

    def __init__(
        self,
        planner: Planner | None = None,
        executor: Executor | None = None,
        approval_enabled: bool = False,
    ) -> None:
        self.planner = planner or Planner()
        self.executor = executor
        self.approval_enabled = approval_enabled
        self._graph: StateGraph | None = None

    def build(self) -> StateGraph:
        """Construct the workflow graph."""
        if self._graph is not None:
            return self._graph

        builder = StateGraph(GraphState)

        async def plan_node(state: GraphState) -> GraphState:
            timer = TimelineTimer()
            context = state["context"]
            session_id = state.get("session_id") or context.session_id
            provider = state.get("provider")

            append_timeline_event(
                state,
                session_id=session_id,
                node="planner",
                event_type="graph.planner.started",
                status="started",
            )

            if provider is None:
                error = "Graph state must carry a provider for graph planning"
                state["error"] = error
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="planner",
                    event_type="graph.planner.failed",
                    status="failed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={"error": error},
                )
                raise ValueError(error)

            try:
                plan = await self.planner.create_plan(provider, state["goal"], context)
                state["plan"] = [_task_to_state(task) for task in plan]
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="planner",
                    event_type="graph.planner.completed",
                    status="completed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={"task_count": len(plan)},
                )
            except Exception as exc:
                state["error"] = _error_to_state("planner", exc)
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="planner",
                    event_type="graph.planner.failed",
                    status="failed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                raise

            return state

        async def execute_node(state: GraphState) -> GraphState:
            timer = TimelineTimer()
            context = state["context"]
            session_id = state.get("session_id") or context.session_id

            append_timeline_event(
                state,
                session_id=session_id,
                node="executor",
                event_type="graph.executor.started",
                status="started",
            )

            if self.approval_enabled and not state.get("approved", False):
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="executor",
                    event_type="graph.approval.required",
                    status="pending",
                    attributes={
                        "approval_required_at": "tool_selection",
                        "message": "Human approval required before tool execution.",
                    },
                )
                raise HumanApprovalRequiredError("Human approval required before tool execution.")

            if self.executor is None:
                error = "GraphBuilder requires an executor instance"
                state["error"] = error
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="executor",
                    event_type="graph.executor.failed",
                    status="failed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={"error": error},
                )
                raise ValueError(error)

            plan = state.get("plan", [])
            results: list[object] = []

            try:
                for step in plan:
                    task = _state_to_task(step)
                    task_timer = TimelineTimer()

                    append_timeline_event(
                        state,
                        session_id=session_id,
                        node="executor",
                        event_type="executor.task.started",
                        status="started",
                        attributes={
                            "task_id": task.id,
                            "assigned_agent": task.assigned_agent,
                            "description": preview_value(task.description, 200),
                        },
                    )

                    result = await self.executor.execute_task(task, context)

                    results.append(
                        {
                            "task_id": task.id,
                            "agent_name": task.assigned_agent,
                            "status": task.status.value,
                            "result_preview": preview_value(result),
                            "result": result,
                        }
                    )

                    append_timeline_event(
                        state,
                        session_id=session_id,
                        node="executor",
                        event_type="executor.task.completed",
                        status="completed",
                        duration_ms=task_timer.elapsed_ms(),
                        attributes={
                            "task_id": task.id,
                            "assigned_agent": task.assigned_agent,
                            "result_preview": preview_value(result),
                        },
                    )

                    state["results"] = results

                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="executor",
                    event_type="graph.executor.completed",
                    status="completed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={"result_count": len(results)},
                )
            except Exception as exc:
                state["error"] = _error_to_state("executor", exc)
                append_timeline_event(
                    state,
                    session_id=session_id,
                    node="executor",
                    event_type="graph.executor.failed",
                    status="failed",
                    duration_ms=timer.elapsed_ms(),
                    attributes={
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                raise

            return state

        builder.add_node("planner", plan_node)
        builder.add_node("executor", execute_node)
        builder.add_edge("planner", "executor")
        builder.add_edge("executor", END)
        builder.set_entry_point("planner")

        self._graph = builder
        return self._graph

    def compile(
        self,
        checkpointer: BaseCheckpointSaver[Any] | bool | None = None,
    ) -> Any:
        """Compile the workflow into an invokable LangGraph app."""
        return self.build().compile(checkpointer=checkpointer)

    async def ainvoke(
        self,
        initial_state: GraphState,
        *,
        checkpointer: BaseCheckpointSaver[Any] | bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> GraphState:
        """Compile and asynchronously invoke the graph."""
        app = self.compile(checkpointer=checkpointer)
        result = await app.ainvoke(initial_state, config=config)
        return cast(GraphState, result)

    def build_with_checkpoint(
        self, db_path: str = "checkpoints.sqlite"
    ) -> tuple[StateGraph, BaseCheckpointSaver[Any]]:
        """Create a graph with an in-memory checkpointer.

        ``db_path`` is retained for API compatibility. SQLite checkpoint
        lifecycle requires an explicitly managed connection; the orchestrator
        owns that concern separately.
        """
        del db_path
        graph = self.build()

        from langgraph.checkpoint.memory import MemorySaver

        return graph, MemorySaver()


def _task_to_state(task: Task) -> dict[str, Any]:
    """Convert a Task dataclass into serializable graph state."""
    return {
        "id": task.id,
        "description": task.description,
        "assigned_agent": task.assigned_agent,
        "dependencies": list(task.dependencies),
        "parallelizable": task.parallelizable,
        "status": task.status.value,
        "result_preview": preview_value(task.result) if task.result is not None else None,
    }


def _state_to_task(state: dict[str, Any]) -> Task:
    """Rebuild a Task dataclass from graph state."""
    status_value = state.get("status", TaskStatus.PENDING.value)

    try:
        status = TaskStatus(status_value)
    except ValueError:
        status = TaskStatus.PENDING

    return Task(
        id=state["id"],
        description=state["description"],
        assigned_agent=state.get("assigned_agent"),
        dependencies=list(state.get("dependencies", [])),
        parallelizable=bool(state.get("parallelizable", False)),
        status=status,
    )


def _error_to_state(node: str, exc: Exception) -> dict[str, Any]:
    """Convert an exception into serializable graph error state."""
    return {
        "node": node,
        "type": type(exc).__name__,
        "message": str(exc),
        "recoverable": False,
    }
