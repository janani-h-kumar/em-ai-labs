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

        final_response = self.synthesize(goal, results)

        # Store the exchange
        history.add_user_message(goal)
        history.add_ai_message(final_response)

        return final_response

    def synthesize(self, goal: str, results: list) -> str:
        """
        Combine task results into one coherent response.

        [Pillar 2] Previously only joined results with newlines when there
        were multiple results, and passed a single result through untouched.
        Now always routes through the LLM when there is at least one result,
        so the final response reads as one coherent answer to the original
        goal rather than a concatenation of agent outputs. Falls back to the
        raw result(s) if the LLM call fails — synthesis failure should not
        lose the work the agents already did.
        """
        if not results:
            return "No result generated."

        if len(results) == 1:
            # Single-task plans are the common case (most goals don't need
            # decomposition) — the agent's own response is already the
            # answer, so skip the extra LLM round trip.
            return str(results[0])

        context_block = "\n\n".join(f"Result {i + 1}:\n{r}" for i, r in enumerate(results))
        prompt = (
            f"Original goal: {goal}\n\n"
            f"Agent results:\n{context_block}\n\n"
            "Synthesise these results into one coherent, conversational response "
            "that directly answers the original goal."
        )

        try:
            return self.provider.chat_completion(prompt)
        except Exception:
            logger.exception(
                "Synthesis LLM call failed goal=%r — falling back to raw results", goal
            )
            return "\n\n".join(str(r) for r in results)
