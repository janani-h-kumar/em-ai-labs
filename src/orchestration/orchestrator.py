"""
Main orchestration engine.
"""

import logging

from src.memory import InProcessMemory
from src.orchestration.executor import Executor
from src.orchestration.models import ExecutionContext
from src.orchestration.planner import Planner
from src.orchestration.react_loop import ReACTLoop
from src.providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates planning, execution, and synthesis.
    """

    def __init__(self, agent_registry, router, provider: BaseLLMProvider):
        self.agent_registry = agent_registry
        self.router = router
        self.provider: BaseLLMProvider = provider
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

        history = self.memory.get_history(session_id)
        memory_context = [
            {"role": m.type, "content": m.content}
            for m in history.messages[-6:]  # last 3 turns for context window
        ]

        context = ExecutionContext(
            session_id=session_id,
            goal=goal,
            memory=memory_context,
        )

        results = await self.react_loop.run(
            provider=self.provider,
            goal=goal,
            context=context,
        )

        # Store the exchange
        history.add_user_message(goal)
        history.add_ai_message(results[0] if results else "")

        return self.synthesize(
            goal,
            results,
        )

    def synthesize(self, goal: str, results: list) -> str:
        if not results:
            return "No result generated."
        if len(results) == 1:
            return str(results[0])
        context_block = "\n\n".join(f"Result {i + 1}:\n{r}" for i, r in enumerate(results))
        prompt = (
            f"Original goal: {goal}\n\n"
            f"Agent results:\n{context_block}\n\n"
            "Synthesise into one coherent, conversational response."
        )
        return self.provider.chat_completion(prompt)
