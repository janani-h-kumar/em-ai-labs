"""
Core orchestration models.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    """
    Lifecycle states for orchestration tasks.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentState(Enum):
    """
    High-level runtime state for the agent orchestration lifecycle.
    """

    PLANNING = "planning"
    TOOL_SELECTION = "tool_selection"
    TOOL_EXECUTION = "tool_execution"
    OBSERVATION = "observation"
    RESPONSE = "response"
    ERROR = "error"


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

    current_state: AgentState = AgentState.PLANNING

    state_history: list[AgentState] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
