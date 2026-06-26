from __future__ import annotations

import time

from src.guardrails import GuardrailConfig, mark_guardrail_violation
from src.guardrails.exceptions import GuardrailViolationError


class ExecutionGuardrail:
    """Bound ReACT execution so loops and runaway runs cannot continue forever."""

    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()

    def validate_task_count(self, tasks):
        if len(tasks) <= self.config.max_tasks_per_execution:
            return tasks

        return tasks[: self.config.max_tasks_per_execution]

    def check_iteration(self, iteration: int) -> None:
        if iteration <= self.config.max_react_iterations:
            return

        violation = GuardrailViolationError(
            code="execution.max_iterations_exceeded",
            public_message=(
                "I stopped this run because it reached the maximum number of reasoning steps."
            ),
            details={
                "limit": self.config.max_react_iterations,
                "iteration": iteration,
            },
        )
        mark_guardrail_violation(violation, limit=self.config.max_react_iterations)
        raise violation

    def check_timeout(self, start_time: float) -> None:
        elapsed_seconds = time.perf_counter() - start_time
        if elapsed_seconds <= self.config.max_execution_seconds:
            return

        violation = GuardrailViolationError(
            code="execution.max_time_exceeded",
            public_message="I stopped this run because it took too long for the local runtime.",
            details={
                "limit_seconds": self.config.max_execution_seconds,
                "elapsed_seconds": round(elapsed_seconds, 3),
            },
        )
        mark_guardrail_violation(violation, limit=self.config.max_execution_seconds)
        raise violation
