"""
ReACT orchestration loop.
"""

import logging
import time
from typing import Any

from src.guardrails import GuardrailConfig, mark_guardrail_violation
from src.guardrails.exceptions import GuardrailViolationError
from src.guardrails.execution_guardrail import ExecutionGuardrail
from src.orchestration.task_graph import TaskGraph

logger = logging.getLogger(__name__)


class ReACTLoop:
    """
    Iterative reasoning and execution loop.

    Reasoning is gated: a single-task plan on iteration 1 has no prior
    observations to react to, so the reasoning LLM call is skipped. Reasoning
    fires when the plan has more than one task (real sequencing decisions exist)
    or once iteration 2+ is reached (real prior results exist to react to).

    Execution is guarded by ExecutionGuardrail — both max iteration count
    and max wall-clock time are checked on every iteration.
    """

    def __init__(self, planner, executor) -> None:
        self.planner = planner
        self.executor = executor

    async def run(
        self,
        provider,
        goal,
        context,
        max_iterations: int = 5,
        reasoning_interval: int = 1,
        max_reasoning_tokens: int = 64,
        guardrail_config: GuardrailConfig | None = None,
    ) -> list[Any]:
        """
        Execute iterative reasoning loop.

        Args:
            provider: BaseLLMProvider for reasoning calls.
            goal: The user goal string.
            context: ExecutionContext — all mutable state lives here.
            max_iterations: Maximum loop iterations (overridden by guardrail_config
                when provided).
            reasoning_interval: How often the reasoning LLM call fires (default every
                iteration when conditions are met).
            max_reasoning_tokens: Token budget for each reasoning call.
            guardrail_config: When provided, max_iterations and timeout limits are read
                from the config rather than the hardcoded defaults.
        """
        # Resolve limits from guardrail config when provided
        _config = guardrail_config or GuardrailConfig()
        effective_max_iterations = _config.max_react_iterations
        guardrail = ExecutionGuardrail(_config)

        start_time = time.perf_counter()

        logger.info(
            "ReACTLoop.start session=%s goal=%s max_iterations=%s",
            context.session_id,
            goal,
            effective_max_iterations,
        )

        tasks = await self.planner.create_plan(provider, goal, context)
        graph = TaskGraph(tasks)
        final_results: list[Any] = []

        if reasoning_interval < 1:
            raise ValueError("reasoning_interval must be >= 1")

        iteration = 0
        while not graph.all_completed() and iteration < effective_max_iterations:
            iteration += 1

            # --- Guardrail checks (both raise GuardrailViolationError on breach) ---
            try:
                guardrail.check_iteration(iteration)
                guardrail.check_timeout(start_time)
            except GuardrailViolationError as e:
                mark_guardrail_violation(e)
                logger.warning(
                    "ReACTLoop guardrail triggered session=%s iteration=%s code=%s",
                    context.session_id,
                    iteration,
                    e.code,
                )
                raise

            # --- Reason step ---
            context.reasoning_history.append(f"Planner invoked iteration={iteration}")

            has_reason_to_think = len(tasks) > 1 or iteration > 1
            interval_gate_passes = (iteration - 1) % reasoning_interval == 0
            should_reason = has_reason_to_think and interval_gate_passes

            if should_reason:
                try:
                    recent_obs = context.observations[-5:]
                    recent_completed = list(context.completed_tasks.items())[-5:]
                    completed_summary = ", ".join(
                        f"{k}:{str(v)[:120]}" for k, v in recent_completed
                    )
                    prompt = (
                        f"Iteration {iteration}\n"
                        f"Goal: {goal}\n"
                        f"Recent observations: {recent_obs}\n"
                        f"Completed (recent): {completed_summary}\n"
                        "Provide a single short reasoning sentence for the next action."
                    )
                    reasoning = provider.chat_completion(
                        prompt,
                        system_prompt="You are a concise planning assistant.",
                        max_tokens=max_reasoning_tokens,
                    )
                    context.reasoning_history.append(str(reasoning))
                    logger.debug(
                        "ReACTLoop.reasoning session=%s iteration=%d reasoning=%s",
                        context.session_id,
                        iteration,
                        str(reasoning)[:200],
                    )
                except GuardrailViolationError:
                    raise
                except Exception as e:
                    logger.exception(
                        "ReACTLoop.reasoning_error session=%s iteration=%d",
                        context.session_id,
                        iteration,
                    )
                    context.reasoning_history.append(f"LLM error: {e}")
            else:
                skip_reason = (
                    "single-task plan with no prior observations"
                    if not has_reason_to_think
                    else "interval gating"
                )
                context.reasoning_history.append(f"Reasoning skipped due to {skip_reason}.")
                logger.debug(
                    "ReACTLoop.reasoning_skipped session=%s iteration=%s task_count=%s reason=%s",
                    context.session_id,
                    iteration,
                    len(tasks),
                    skip_reason,
                )

            # --- Execute ready tasks ---
            ready = graph.get_ready_tasks()
            logger.info(
                "ReACTLoop.iteration session=%s iteration=%s ready_tasks=%s",
                context.session_id,
                iteration,
                len(ready),
            )

            if not ready:
                context.observations.append("No ready tasks; breaking")
                logger.warning(
                    "ReACTLoop.no_ready session=%s iteration=%s",
                    context.session_id,
                    iteration,
                )
                break

            if len(ready) == 1:
                logger.info(
                    "ReACTLoop.execute.serial session=%s iteration=%s task_id=%s",
                    context.session_id,
                    iteration,
                    ready[0].id,
                )
                result = await self.executor.execute_task(ready[0], context)
                graph.mark_completed(ready[0].id, result)
                context.observations.append(f"Executed task {ready[0].id} serially")
            else:
                logger.info(
                    "ReACTLoop.execute.parallel session=%s iteration=%s tasks=%s",
                    context.session_id,
                    iteration,
                    len(ready),
                )
                results = await self.executor.execute_parallel(ready, context)
                for task, result in zip(ready, results, strict=True):
                    graph.mark_completed(task.id, result)
                    context.observations.append(f"Executed task {task.id} in parallel")

            for t in ready:
                final_results.append(t.result)
                context.completed_tasks[t.id] = t.result
                context.task_state[t.id] = t.status

            logger.info(
                "ReACTLoop.observe session=%s iteration=%s completed_tasks=%s",
                context.session_id,
                iteration,
                len(context.completed_tasks),
            )

            context.metadata.setdefault("react", {})
            context.metadata["react"][f"iter_{iteration}"] = {
                "observations": list(context.observations),
                "reasoning": list(context.reasoning_history),
                "completed_tasks": dict(context.completed_tasks),
            }

        logger.info(
            "ReACTLoop.finished session=%s iterations=%s results=%s",
            context.session_id,
            iteration,
            len(final_results),
        )

        return final_results
