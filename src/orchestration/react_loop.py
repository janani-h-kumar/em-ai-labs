"""
ReACT orchestration loop.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.orchestration.task_graph import TaskGraph

logger = logging.getLogger(__name__)


class ReACTLoop:
    """
    Iterative reasoning and execution loop.

    Initial implementation is intentionally lightweight.

    [Latency optimisation] Reasoning is now gated on whether there's
    anything to reason about — a single-task plan on its first iteration
    has no prior observations to react to, so the reasoning LLM call adds
    latency without changing behaviour. Reasoning still fires whenever the
    plan has more than one task (real sequencing decisions exist) or once
    iteration 2+ is reached (real prior results exist to react to).
    """

    def __init__(
        self,
        planner,
        executor,
    ):
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
    ):
        """
        Execute iterative reasoning loop.
        """
        exec_state = ExecutionState(session_id=context.session_id, goal=goal)
        logger.info(
            "ReACTLoop.start session=%s goal=%s max_iterations=%s",
            exec_state.session_id,
            goal,
            max_iterations,
        )

        tasks = await self.planner.create_plan(provider, goal, context)
        graph = TaskGraph(tasks)
        final_results: list[Any] = []

        if reasoning_interval < 1:
            raise ValueError("reasoning_interval must be >= 1")

        while not graph.all_completed() and exec_state.iteration < max_iterations:
            exec_state.iteration += 1

            # Reason step: ask the LLM to (re)consider the plan if there's
            # something worth reasoning about.
            exec_state.reasoning.append(f"Planner invoked iteration={exec_state.iteration}")

            # FIX [latency]: was `exec_state.iteration == 1 or (...)`, which
            # guaranteed a reasoning LLM call on the very first iteration of
            # every request — including single-task plans, where there are
            # no prior observations yet for the model to reason about. That
            # call was pure latency (~3s) with zero effect on the outcome.
            #
            # New rule: reason when the plan has more than one task (a real
            # sequencing/adaptation decision exists even on iteration 1), or
            # once we're past iteration 1 (real observations now exist).
            # Interval gating (when configured) still applies on top of that.
            has_reason_to_think = len(tasks) > 1 or exec_state.iteration > 1
            interval_gate_passes = (exec_state.iteration - 1) % reasoning_interval == 0
            should_reason = has_reason_to_think and interval_gate_passes

            if should_reason:
                try:
                    recent_obs = exec_state.observations[-5:]
                    recent_completed = list(exec_state.completed_tasks.items())[-5:]
                    completed_summary = ", ".join(
                        f"{k}:{str(v)[:120]}" for k, v in recent_completed
                    )
                    prompt = (
                        f"Iteration {exec_state.iteration}\n"
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
                    exec_state.reasoning.append(str(reasoning))
                    logger.debug(
                        "ReACTLoop.reasoning session=%s iteration=%d reasoning=%s",
                        exec_state.session_id,
                        exec_state.iteration,
                        (reasoning if isinstance(reasoning, str) else str(reasoning))[:200],
                    )
                except Exception as e:
                    logger.exception(
                        "ReACTLoop.reasoning_error session=%s iteration=%d",
                        exec_state.session_id,
                        exec_state.iteration,
                    )
                    exec_state.reasoning.append(f"LLM error: {e}")
            else:
                if not has_reason_to_think:
                    skip_reason = "single-task plan with no prior observations"
                else:
                    skip_reason = "interval gating"
                exec_state.reasoning.append(f"Reasoning skipped due to {skip_reason}.")
                logger.debug(
                    "ReACTLoop.reasoning_skipped session=%s iteration=%s task_count=%s reason=%s",
                    exec_state.session_id,
                    exec_state.iteration,
                    len(tasks),
                    skip_reason,
                )

            ready = graph.get_ready_tasks()
            logger.info(
                "ReACTLoop.iteration session=%s iteration=%s ready_tasks=%s",
                exec_state.session_id,
                exec_state.iteration,
                len(ready),
            )
            if not ready:
                exec_state.observations.append("No ready tasks; breaking")
                logger.warning(
                    "ReACTLoop.no_ready session=%s iteration=%s",
                    exec_state.session_id,
                    exec_state.iteration,
                )
                break

            if len(ready) == 1:
                logger.info(
                    "ReACTLoop.execute.serial session=%s iteration=%s task_id=%s",
                    exec_state.session_id,
                    exec_state.iteration,
                    ready[0].id,
                )
                result = await self.executor.execute_task(ready[0], context)
                graph.mark_completed(ready[0].id, result)
                exec_state.observations.append(f"Executed task {ready[0].id} serially")
            else:
                logger.info(
                    "ReACTLoop.execute.parallel session=%s iteration=%s tasks=%s",
                    exec_state.session_id,
                    exec_state.iteration,
                    len(ready),
                )
                results = await self.executor.execute_parallel(ready, context)
                for task, result in zip(ready, results, strict=True):
                    graph.mark_completed(task.id, result)
                    exec_state.observations.append(f"Executed task {task.id} in parallel")
                    logger.debug(
                        "ReACTLoop.task.completed session=%s iteration=%s task_id=%s",
                        exec_state.session_id,
                        exec_state.iteration,
                        task.id,
                    )

            for t in ready:
                final_results.append(t.result)
                exec_state.completed_tasks[t.id] = t.result

            logger.info(
                "ReACTLoop.observe session=%s iteration=%s completed_tasks=%s",
                exec_state.session_id,
                exec_state.iteration,
                len(exec_state.completed_tasks),
            )

            context.metadata.setdefault("react", {})
            context.metadata["react"][f"iter_{exec_state.iteration}"] = {
                "observations": list(exec_state.observations),
                "reasoning": list(exec_state.reasoning),
                "completed_tasks": dict(exec_state.completed_tasks),
            }

        logger.info(
            "ReACTLoop.finished session=%s iterations=%s results=%s",
            exec_state.session_id,
            exec_state.iteration,
            len(final_results),
        )

        return final_results


@dataclass
class ExecutionState:
    session_id: str
    goal: str
    iteration: int = 0
    observations: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    completed_tasks: dict[str, Any] = field(default_factory=dict)
