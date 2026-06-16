"""
Task planner for goal decomposition.
"""

import logging
from typing import TypedDict
from uuid import uuid4

from src.orchestration.models import ExecutionContext, Task
from src.providers.base_provider import BaseLLMProvider


class PlanStep(TypedDict):
    description: str
    agent: str
    parallelizable: bool


logger = logging.getLogger(__name__)


class Planner:
    """
    Responsible for decomposing goals into executable tasks.
    """

    async def create_plan(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[Task]:
        """
        # prompt = f
        Break the following goal into 1-3 discrete tasks.
        Each task should be assignable to a single agent.
        Respond as JSON: [{"description": "...", "agent": "...", "parallelizable": false}]

        Goal: {goal}
        """

        """ TODO revisit later 
        self.provider = provider
        raw = self.provider.chat_completion(prompt)
        steps = json.loads(raw)
        """
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
