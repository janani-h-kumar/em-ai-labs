"""
Core orchestration models.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """
    Lifecycle states for orchestration tasks.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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

    memory: list[str] = field(default_factory=list)

    completed_tasks: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)
