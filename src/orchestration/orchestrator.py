"""
Main orchestration engine.
"""

import logging

from src.memory import InProcessMemory
from src.orchestration.executor import Executor
from src.orchestration.models import ExecutionContext
from src.orchestration.planner import Planner
from src.orchestration.react_loop import ReACTLoop

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates planning, execution, and synthesis.
    """

    def __init__(
        self,
        agent_registry,
        router,
    ):
        self.agent_registry = agent_registry
        self.router = router

        self.memory = InProcessMemory()

        self.planner = Planner()

        self.executor = Executor(
            agent_registry=self.agent_registry,
            router=self.router,
        )

        self.react_loop = ReACTLoop(
            planner=self.planner,
            executor=self.executor,
        )

    async def run(
        self,
        goal: str,
        session_id: str,
    ) -> str:
        """
        Execute orchestration lifecycle.
        """

        logger.info(
            "Starting orchestration",
            extra={
                "extra_data": {
                    "goal": goal,
                    "session_id": session_id,
                }
            },
        )

        memory_context = []

        context = ExecutionContext(
            session_id=session_id,
            goal=goal,
            memory=memory_context,
        )

        results = await self.react_loop.run(
            goal=goal,
            context=context,
        )

        final_response = self.synthesize(
            goal,
            results,
        )

        return final_response

    def synthesize(
        self,
        goal: str,
        results: list,
    ) -> str:
        """
        Combine execution outputs into final response.
        """

        if not results:
            return "No result generated."

        return "\n".join(str(result) for result in results)
