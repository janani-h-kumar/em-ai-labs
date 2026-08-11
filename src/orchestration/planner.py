"""
Task planner for goal decomposition.
"""

import json
import logging
import re
import time
from typing import TypedDict
from uuid import uuid4

from src.guardrails import GuardrailConfig, mark_guardrail_violation
from src.guardrails.exceptions import GuardrailViolationError
from src.guardrails.output_guardrail import OutputGuardrail
from src.observability.tracing import create_span
from src.orchestration.models import ExecutionContext, Task
from src.providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

MAX_PLAN_STEPS = 3

_COORDINATION_SIGNALS = (
    " and then ",
    " then ",
    " after that ",
    " also ",
    " as well as ",
    " followed by ",
    "; ",
)
_SHORT_GOAL_WORD_THRESHOLD = 12


class PlanStep(TypedDict):
    description: str
    agent: str | None
    parallelizable: bool


class Planner:
    """
    Responsible for decomposing goals into executable tasks.

    Falls back to a single-task plan if the heuristic says single-intent,
    if the LLM call fails, or if the response cannot be parsed as a valid plan.
    """

    def __init__(self, guardrail_config: GuardrailConfig | None = None) -> None:
        # OutputGuardrail handles planner JSON validation and step-count capping.
        self._output_guardrail = OutputGuardrail(guardrail_config or GuardrailConfig())

    async def create_plan(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[Task]:
        """Decompose a goal into executable tasks, skipping the LLM call when unnecessary."""
        start_time = time.perf_counter()

        with create_span(
            "planner.create_plan",
            session_id=context.session_id,
            goal=goal,
            decision="planner",
        ) as span:
            if self._looks_single_intent(goal):
                logger.debug(
                    "Planner heuristic: single-intent goal, skipping LLM planning call goal=%r",
                    goal,
                )
                span.set_attribute("planner.heuristic_skip", True)
                span.set_attribute("decision", "heuristic_skip")
                steps: list[PlanStep] | None = None
            else:
                span.set_attribute("planner.heuristic_skip", False)
                span.set_attribute("decision", "llm_plan")
                steps = await self._plan_via_llm(provider, goal, context)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            span.set_attribute("planner_latency_ms", duration_ms)
            logger.info(
                "Planner completed",
                extra={
                    "extra_data": {
                        "session_id": context.session_id,
                        "planner_latency_ms": duration_ms,
                    }
                },
            )

        if steps is None:
            if not self._looks_single_intent(goal):
                logger.warning(
                    "Planner falling back to single-task plan goal=%r session=%s",
                    goal,
                    context.session_id,
                )
            steps = [{"description": goal, "agent": None, "parallelizable": False}]

        return [
            Task(
                id=str(uuid4()),
                description=s["description"],
                assigned_agent=s.get("agent"),
                parallelizable=s.get("parallelizable", False),
            )
            for s in steps
        ]

    def _looks_single_intent(self, goal: str) -> bool:
        """Cheap heuristic: does this goal show signs of being compound?"""
        if not goal or not goal.strip():
            return True

        normalised = f" {goal.lower().strip()} "

        if any(signal in normalised for signal in _COORDINATION_SIGNALS):
            return False

        if len(goal.split()) > _SHORT_GOAL_WORD_THRESHOLD:
            return False

        return True

    async def _plan_via_llm(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[PlanStep] | None:
        """Ask the LLM to decompose the goal into a JSON array of steps."""
        memory_summary = self._summarise_memory(context)
        prompt = (
            f"Break the following goal into 1 to {MAX_PLAN_STEPS} discrete, "
            "independently describable tasks. Most goals only need 1 task — "
            "only split into multiple tasks if the goal clearly asks for "
            "distinct pieces of work.\n\n"
            f"{memory_summary}"
            f"Goal: {goal}\n\n"
            "Respond with ONLY a JSON array, no other text, no markdown code "
            "fences, no explanation. Each item must have this exact shape:\n"
            '[{"description": "...", "agent": null, "parallelizable": false}]\n\n'
            'Leave "agent" as null unless you are certain which agent should '
            "handle the task — routing will be decided automatically otherwise."
        )

        try:
            raw = provider.chat_completion(
                prompt,
                system_prompt=(
                    "You are a task planning assistant. You respond with valid "
                    "JSON only — never prose, never markdown, never explanations."
                ),
            )
        except Exception:
            logger.exception("Planner LLM call failed goal=%r session=%s", goal, context.session_id)
            return None

        return self._parse_plan_response(raw)

    def _parse_plan_response(self, raw: object) -> list[PlanStep] | None:
        """
        Tolerantly parse the LLM's plan response into a list of PlanStep.

        Strips markdown fences, extracts the first JSON array from any surrounding
        prose, then delegates validation and step-count capping to OutputGuardrail.
        Returns None if no valid plan can be extracted.
        """
        if not isinstance(raw, str) or not raw.strip():
            return None

        text = raw.strip()

        # Strip markdown code fences
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Extract first [...] array in case of stray prose around it
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            text = array_match.group(0)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Planner could not parse LLM response as JSON raw=%r",
                raw[:300] if isinstance(raw, str) else raw,
            )
            return None

        # Delegate to OutputGuardrail — handles single-object, validates fields,
        # caps step count to max_tasks_per_execution
        try:
            validated = self._output_guardrail.validate_planner_steps(raw, parsed)
        except GuardrailViolationError as e:
            mark_guardrail_violation(e)
            logger.warning(
                "Output guardrail blocked plan response",
                extra={"extra_data": {"guardrail_code": e.code, **e.details}},
            )
            return None

        if validated is None:
            return None

        # Cast the validated list to PlanStep — OutputGuardrail guarantees the shape
        return [
            PlanStep(
                description=step["description"],
                agent=step.get("agent"),
                parallelizable=bool(step.get("parallelizable", False)),
            )
            for step in validated
        ]

    def _summarise_memory(self, context: ExecutionContext) -> str:
        """Build an optional memory context block for the planning prompt."""
        memory_turns = getattr(context, "memory", None) or []
        if not memory_turns:
            return ""
        recent = memory_turns[-4:]
        lines = [f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in recent]
        return "Recent conversation:\n" + "\n".join(lines) + "\n\n"
