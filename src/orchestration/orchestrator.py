"""
Main orchestration engine.
"""

import logging
import time

from src.guardrails import GuardrailConfig
from src.guardrails.output_guardrail import OutputGuardrail
from src.memory.base_memory import BaseMemory
from src.observability.tracing import create_span
from src.orchestration.executor import Executor
from src.orchestration.models import ExecutionContext
from src.orchestration.planner import Planner
from src.orchestration.react_loop import ReACTLoop
from src.providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates planning, execution, and synthesis.

    Guardrails applied:
    - ExecutionGuardrail: enforced inside ReACTLoop (iteration + timeout)
    - OutputGuardrail: validate_final_response() applied before returning
    """

    def __init__(
        self,
        agent_registry,
        router,
        provider: BaseLLMProvider,
        memory: BaseMemory,
        guardrail_config: GuardrailConfig | None = None,
    ) -> None:
        self.agent_registry = agent_registry
        self.router = router
        self.provider: BaseLLMProvider = provider
        self.memory: BaseMemory = memory
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.output_guardrail = OutputGuardrail(self.guardrail_config)

        self.planner = Planner()
        self.executor = Executor(
            agent_registry=self.agent_registry,
            router=self.router,
        )
        self.react_loop = ReACTLoop(
            planner=self.planner,
            executor=self.executor,
        )

    async def run(self, goal: str, session_id: str) -> str:
        """Execute orchestration lifecycle."""
        start_time = time.perf_counter()
        logger.info(
            "Starting orchestration",
            extra={"extra_data": {"goal": goal, "session_id": session_id}},
        )

        with create_span("orchestrator.run", session_id=session_id, goal=goal) as span:
            # Memory retrieval
            memory_start = time.perf_counter()
            history = self.memory.get_history(session_id)
            memory_latency_ms = round((time.perf_counter() - memory_start) * 1000, 1)
            span.set_attribute("memory_latency_ms", memory_latency_ms)
            logger.info(
                "Memory retrieval completed",
                extra={
                    "extra_data": {
                        "session_id": session_id,
                        "memory_latency_ms": memory_latency_ms,
                    }
                },
            )

            memory_context = [{"role": m.type, "content": m.content} for m in history.messages[-6:]]

            context = ExecutionContext(
                session_id=session_id,
                goal=goal,
                memory=memory_context,
            )

            # ReACT loop — guardrail_config drives iteration + timeout limits
            results = await self.react_loop.run(
                provider=self.provider,
                goal=goal,
                context=context,
                guardrail_config=self.guardrail_config,
            )

            raw_response = self.synthesize(goal, results)

            # Output guardrail — validate before returning to the caller.
            # validate_final_response raises GuardrailViolationError on empty
            # output; ApplicationService catches that and returns the public
            # message to the user.
            final_response = self.output_guardrail.validate_final_response(raw_response)

            # Store exchange in memory
            history.add_user_message(goal)
            history.add_ai_message(final_response)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            span.set_attribute("orchestrator_latency_ms", duration_ms)
            logger.info(
                "Orchestration completed",
                extra={
                    "extra_data": {
                        "session_id": session_id,
                        "orchestrator_latency_ms": duration_ms,
                    }
                },
            )

            return final_response

    def synthesize(self, goal: str, results: list) -> str:
        """Combine task results into one coherent response."""
        if not results:
            return ""  # output_guardrail catches empty and raises

        if len(results) == 1:
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
