"""
Task planner for goal decomposition.
"""

import logging
from uuid import uuid4

from src.orchestration.models import ExecutionContext, Task

logger = logging.getLogger(__name__)


class Planner:
    """
    Responsible for decomposing goals into executable tasks.
    """

    async def create_plan(
        self,
        goal: str,
        context: ExecutionContext,
    ) -> list[Task]:
        """
        Create an execution plan from a goal.

        Initial implementation:
        - simple single-task plan
        - later evolves into LLM-based decomposition
        """

        logger.info(
            "Creating execution plan",
            extra={
                "extra_data": {
                    "session_id": context.session_id,
                    "goal": goal,
                }
            },
        )

        task = Task(
            id=str(uuid4()),
            description=goal,
        )

        return [task]
