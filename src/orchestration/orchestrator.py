"""
Main orchestration engine.
"""

import logging
import time
from pathlib import Path
from typing import Any

from src.guardrails import GuardrailConfig
from src.guardrails.output_guardrail import OutputGuardrail
from src.memory.base_memory import BaseMemory
from src.observability.timeline import (
    TimelineTimer,
    append_state_transition,
    append_timeline_event,
)
from src.observability.tracing import create_span
from src.orchestration.executor import Executor
from src.orchestration.graph_builder import GraphBuilder
from src.orchestration.models import AgentState, ExecutionContext
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
        config_manager: Any | None = None,
    ) -> None:
        self.agent_registry = agent_registry
        self.router = router
        self.provider: BaseLLMProvider = provider
        self.memory: BaseMemory = memory
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.config_manager = config_manager
        self.output_guardrail = OutputGuardrail(self.guardrail_config)

        self.planner = Planner()
        self.executor = Executor(
            agent_registry=self.agent_registry,
            router=self.router,
        )
        self.graph_builder = GraphBuilder(
            planner=self.planner,
            executor=self.executor,
            approval_enabled=self._approval_enabled(),
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
            context.current_state = AgentState.PLANNING
            context.state_history.append(AgentState.PLANNING)
            append_state_transition(
                context,
                session_id=session_id,
                node="orchestrator",
                from_state="none",
                to_state=context.current_state.value,
            )
            append_timeline_event(
                context,
                session_id=session_id,
                node="memory",
                event_type="memory.loaded",
                status="completed",
                duration_ms=memory_latency_ms,
                attributes={"message_count": len(memory_context)},
            )

            # Runtime selection: LangGraph is optional; ReACT remains the default.
            runtime_mode = self._orchestration_mode()
            span.set_attribute("orchestration.mode", runtime_mode)

            if runtime_mode == "langgraph":
                try:
                    results = await self._run_langgraph(goal, session_id, context)
                except Exception as exc:
                    context.current_state = AgentState.ERROR
                    context.state_history.append(AgentState.ERROR)
                    append_state_transition(
                        context,
                        session_id=session_id,
                        node="orchestrator",
                        from_state=AgentState.OBSERVATION.value,
                        to_state=AgentState.ERROR.value,
                    )
                    if not self._fallback_to_react():
                        raise
                    logger.exception(
                        "LangGraph execution failed; falling back to ReACT",
                        extra={
                            "extra_data": {
                                "session_id": session_id,
                                "error_type": type(exc).__name__,
                            }
                        },
                    )
                    span.set_attribute("fallback.used", True)
                    append_timeline_event(
                        context,
                        session_id=session_id,
                        node="graph",
                        event_type="graph.fallback_to_react",
                        status="completed",
                        attributes={
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    results = await self._run_react(goal, context)
            else:
                results = await self._run_react(goal, context)

            context.current_state = AgentState.RESPONSE
            context.state_history.append(AgentState.RESPONSE)
            append_state_transition(
                context,
                session_id=session_id,
                node="orchestrator",
                from_state=AgentState.OBSERVATION.value,
                to_state=AgentState.RESPONSE.value,
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
            append_timeline_event(
                context,
                session_id=session_id,
                node="memory",
                event_type="memory.persisted",
                status="completed",
                attributes={"exchange_count": 1},
            )

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

    async def _run_react(self, goal: str, context: ExecutionContext) -> list[Any]:
        """Run the legacy ReACT orchestration path."""
        previous_state = context.current_state.value
        context.current_state = AgentState.PLANNING
        context.state_history.append(AgentState.PLANNING)
        append_state_transition(
            context,
            session_id=context.session_id,
            node="react",
            from_state=previous_state,
            to_state=context.current_state.value,
        )
        append_timeline_event(
            context,
            session_id=context.session_id,
            node="react",
            event_type="react.started",
            status="started",
        )
        timer = TimelineTimer()
        results = await self.react_loop.run(
            provider=self.provider,
            goal=goal,
            context=context,
            guardrail_config=self.guardrail_config,
        )
        append_state_transition(
            context,
            session_id=context.session_id,
            node="react",
            from_state=AgentState.PLANNING.value,
            to_state=AgentState.OBSERVATION.value,
            duration_ms=timer.elapsed_ms(),
        )
        append_timeline_event(
            context,
            session_id=context.session_id,
            node="react",
            event_type="react.completed",
            status="completed",
            duration_ms=timer.elapsed_ms(),
            attributes={"result_count": len(results)},
        )
        return results

    async def _run_langgraph(
        self, goal: str, session_id: str, context: ExecutionContext
    ) -> list[Any]:
        """Run the LangGraph orchestration path."""
        timer = TimelineTimer()
        append_timeline_event(
            context,
            session_id=session_id,
            node="graph",
            event_type="graph.started",
            status="started",
        )
        previous_state = context.current_state.value
        context.current_state = AgentState.PLANNING
        context.state_history.append(AgentState.PLANNING)
        append_state_transition(
            context,
            session_id=session_id,
            node="graph",
            from_state=previous_state,
            to_state=context.current_state.value,
            duration_ms=timer.elapsed_ms(),
        )
        checkpointer = self._build_langgraph_checkpointer()
        state = await self.graph_builder.ainvoke(
            {
                "session_id": session_id,
                "goal": goal,
                "context": context,
                "provider": self.provider,
                "timeline": list(context.metadata.get("timeline", [])),
                "metadata": {},
            },
            checkpointer=checkpointer,
            config={"configurable": {"thread_id": session_id}},
        )
        context.metadata["timeline"] = state.get("timeline", context.metadata.get("timeline", []))
        previous_state = context.current_state.value
        context.current_state = AgentState.OBSERVATION
        context.state_history.append(AgentState.OBSERVATION)
        append_state_transition(
            context,
            session_id=session_id,
            node="graph",
            from_state=previous_state,
            to_state=context.current_state.value,
            duration_ms=timer.elapsed_ms(),
        )
        append_timeline_event(
            context,
            session_id=session_id,
            node="graph",
            event_type="graph.completed",
            status="completed",
            duration_ms=timer.elapsed_ms(),
            attributes={"result_count": len(state.get("results", []))},
        )
        return [
            result.get("result") if isinstance(result, dict) and "result" in result else result
            for result in state.get("results", [])
        ]

    def _orchestration_mode(self) -> str:
        mode = self._config_get("runtime.orchestration", "react")
        if not isinstance(mode, str):
            return "react"
        mode = mode.strip().lower()
        return mode if mode in {"react", "langgraph"} else "react"

    def _fallback_to_react(self) -> bool:
        return bool(self._config_get("runtime.langgraph.fallback_to_react", False))

    def _approval_enabled(self) -> bool:
        return bool(self._config_get("runtime.langgraph.approval.enabled", False))

    def _build_langgraph_checkpointer(self) -> object | None:
        enabled = bool(self._config_get("runtime.langgraph.checkpoint.enabled", False))
        if not enabled:
            return None

        backend = self._config_get("runtime.langgraph.checkpoint.backend", "memory")
        if not isinstance(backend, str):
            backend = "memory"
        backend = backend.strip().lower()

        if backend == "memory":
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()

        if backend == "sqlite":
            db_path = self._config_get(
                "runtime.langgraph.checkpoint.db_path",
                "./data/langgraph_checkpoints.sqlite",
            )
            Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
            except ImportError as exc:
                raise RuntimeError(
                    "SQLite LangGraph checkpointing requires langgraph-checkpoint-sqlite"
                ) from exc

            if hasattr(SqliteSaver, "from_conn_string"):
                return SqliteSaver.from_conn_string(str(db_path))
            return SqliteSaver(str(db_path))

        raise ValueError(f"Unsupported LangGraph checkpoint backend: {backend}")

    def _config_get(self, key: str, default: Any = None) -> Any:
        if self.config_manager is None:
            return default
        getter = getattr(self.config_manager, "get", None)
        if not callable(getter):
            return default
        return getter(key, default)

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
