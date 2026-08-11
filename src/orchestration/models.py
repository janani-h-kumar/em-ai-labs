"""
Core orchestration models.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.observability.timeline import append_state_transition


class TaskStatus(Enum):
    """
    Lifecycle states for orchestration tasks.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionState(Enum):
    """
    High-level lifecycle states for orchestrator execution.
    """

    STARTED = "started"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_EXECUTION_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.STARTED: {ExecutionState.PLANNING, ExecutionState.FAILED},
    ExecutionState.PLANNING: {
        ExecutionState.EXECUTING,
        ExecutionState.OBSERVING,
        ExecutionState.FAILED,
    },
    ExecutionState.EXECUTING: {ExecutionState.OBSERVING, ExecutionState.FAILED},
    ExecutionState.OBSERVING: {
        ExecutionState.PLANNING,
        ExecutionState.COMPLETED,
        ExecutionState.FAILED,
    },
    ExecutionState.COMPLETED: {ExecutionState.FAILED},
    ExecutionState.FAILED: set(),
}


def _validate_execution_transition(current: ExecutionState, next_state: ExecutionState) -> None:
    if next_state == ExecutionState.FAILED:
        return
    allowed = _ALLOWED_EXECUTION_TRANSITIONS.get(current, set())
    if next_state not in allowed:
        raise ValueError(f"Invalid execution transition {current.value} -> {next_state.value}")


@dataclass
class Task:
    """
    Represents a unit of work for an agent.
    """

    id: str
    description: str

    assigned_agent: str | None = None

    dependencies: list[str] = field(default_factory=list)

    parallelizable: bool = False

    status: TaskStatus = TaskStatus.PENDING

    result: Any = None


@dataclass
class ExecutionContext:
    """
    Shared execution context across orchestration lifecycle.
    """

    session_id: str

    goal: str

    memory: list[dict[str, Any]] = field(default_factory=list)

    observations: list[str] = field(default_factory=list)

    reasoning_history: list[str] = field(default_factory=list)

    task_state: dict[str, TaskStatus] = field(default_factory=dict)

    completed_tasks: dict[str, Any] = field(default_factory=dict)

    current_state: ExecutionState = ExecutionState.STARTED

    state_history: list[ExecutionState] = field(default_factory=list)

    iteration: int = 0

    task_id: str | None = None

    decision: dict[str, Any] | None = None

    error: dict[str, Any] | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def transition_to(
        self,
        next_state: ExecutionState,
        *,
        decision: dict[str, Any] | None = None,
        task_id: str | None = None,
        error: dict[str, Any] | None = None,
        node: str = "orchestrator",
        duration_ms: float | None = None,
    ) -> None:
        """Transition the execution context to a new validated state."""
        _validate_execution_transition(self.current_state, next_state)

        previous_state = self.current_state
        self.current_state = next_state
        self.state_history.append(next_state)

        if decision is not None:
            self.decision = decision
        if task_id is not None:
            self.task_id = task_id
        if error is not None:
            self.error = error

        if next_state == ExecutionState.PLANNING:
            if previous_state == ExecutionState.STARTED:
                self.iteration = 1
            elif previous_state == ExecutionState.OBSERVING:
                self.iteration += 1

        append_state_transition(
            self,
            session_id=self.session_id,
            node=node,
            from_state=previous_state.value,
            to_state=next_state.value,
            duration_ms=duration_ms,
            attributes={
                "decision": self.decision,
                "task_id": self.task_id,
                "error": self.error,
                "iteration": self.iteration,
            },
        )
