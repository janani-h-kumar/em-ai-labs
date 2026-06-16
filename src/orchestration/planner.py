"""
Task planner for goal decomposition.
"""

import logging
from typing import TypedDict
from uuid import uuid4

from src.orchestration.models import ExecutionContext, Task
from src.providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class PlanStep(TypedDict):
    description: str
    agent: str | None  # FIX: was typed str, but default is None — mypy error
    parallelizable: bool


class Planner:
    """
    Responsible for decomposing goals into executable tasks.

    Currently returns a single-task plan; LLM-driven decomposition planned for Phase 4.
    """

    async def create_plan(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[Task]:
        """Decompose a goal into executable tasks. Single-task for now; LLM decomposition in Phase 4."""

        # TODO Phase 4: replace with LLM-driven decomposition
        # prompt = f"""
        # Break the following goal into 1-3 discrete tasks.
        # Each task should be assignable to a single agent.
        # Available agents: weather_agent, general
        # Respond as JSON: [{{"description": "...", "agent": "...", "parallelizable": false}}]
        # Goal: {goal}
        # """
        # raw = provider.chat_completion(prompt)
        # steps = json.loads(raw)

        # By default do not assign a concrete agent here; leave routing to the Router
        steps: list[PlanStep] = [{"description": goal, "agent": None, "parallelizable": False}]

        return [
            Task(
                id=str(uuid4()),
                description=s["description"],
                assigned_agent=s.get("agent"),
                parallelizable=s.get("parallelizable", False),
            )
            for s in steps
        ]
