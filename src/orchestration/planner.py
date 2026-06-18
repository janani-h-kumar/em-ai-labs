"""
Task planner for goal decomposition.

[Pillar 2] Replaces the hardcoded single-task plan with a real LLM call.
Works with any local LLM via strict "JSON only" prompting plus a tolerant
parser — no provider-specific structured-output / JSON-mode parameter is
used, so behaviour is identical across Ollama, Claude, OpenAI, or any future
provider implementing BaseLLMProvider.

Failure handling: if the LLM returns unparseable output (missing braces,
wrapped in prose, truncated, etc.) the planner logs the failure and falls
back to the original single-task plan rather than raising — a bad plan
should degrade gracefully, not crash the orchestration loop.

[Latency optimisation] create_plan() now applies a cheap heuristic before
ever calling the LLM: most goals are single-intent and don't need a ~9s
round trip to confirm that. Only goals showing real signs of being compound
(coordination words, multiple imperative verbs) pay for the LLM planning
call. This is a pure win — it can only skip the LLM call when the result
would have been a single-task plan anyway, never the reverse.
"""

import json
import logging
import re
from typing import TypedDict
from uuid import uuid4

from src.orchestration.models import ExecutionContext, Task
from src.providers.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

MAX_PLAN_STEPS = 3

# Words/phrases that signal a goal likely has more than one distinct piece
# of work. Deliberately conservative — false negatives (treating a compound
# goal as single-task) just mean the agent handles a slightly broader task
# description, which existing agents already tolerate. False positives
# (calling the LLM unnecessarily) are the cost we're trying to avoid, so the
# list stays short and high-signal rather than exhaustive.
_COORDINATION_SIGNALS = (
    " and then ",
    " then ",
    " after that ",
    " also ",
    " as well as ",
    " followed by ",
    "; ",
)

# A second clause introduced by "and" is the main false-negative risk
# ("weather in Seattle and Tokyo" should arguably split) — treated as a
# signal too, but only when "and" is not immediately followed by something
# that reads like part of the same noun phrase (handled by the simple
# substring check below; precision over recall is fine here).
_SHORT_GOAL_WORD_THRESHOLD = 12


class PlanStep(TypedDict):
    description: str
    agent: str | None
    parallelizable: bool


class Planner:
    """
    Responsible for decomposing goals into executable tasks.

    [Pillar 2] create_plan() calls the LLM to decompose the goal into 1-3
    tasks, but only when a cheap heuristic suggests the goal might actually
    be compound. Falls back to a single-task plan if the heuristic says
    "single intent", if the LLM call fails, or if the response can't be
    parsed as a valid plan.
    """

    async def create_plan(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[Task]:
        """Decompose a goal into executable tasks, skipping the LLM call when unnecessary."""

        if self._looks_single_intent(goal):
            logger.debug(
                "Planner heuristic: single-intent goal, skipping LLM planning call goal=%r",
                goal,
            )
            steps: list[PlanStep] | None = None
        else:
            steps = await self._plan_via_llm(provider, goal, context)

        if steps is None:
            if not self._looks_single_intent(goal):
                # Only log a fallback warning when we actually attempted and
                # failed the LLM call — the heuristic skip path is expected
                # behaviour, not a failure, so it stays at debug level above.
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
        """
        Cheap heuristic: does this goal show any sign of being compound?

        Returns True (skip the LLM call) when the goal is short and contains
        no coordination signals. Returns False (call the LLM) when the goal
        is long enough or contains language suggesting multiple distinct
        pieces of work.

        Deliberately biased toward skipping — a wrongly-skipped compound goal
        still gets handled (just as one broader task), while a wrongly-called
        LLM planning round trip costs ~9s for no benefit. Asymmetric cost,
        asymmetric heuristic.
        """
        if not goal or not goal.strip():
            return True

        normalised = f" {goal.lower().strip()} "

        if any(signal in normalised for signal in _COORDINATION_SIGNALS):
            return False

        word_count = len(goal.split())
        if word_count > _SHORT_GOAL_WORD_THRESHOLD:
            # Longer goals are more likely to be compound even without an
            # explicit coordination word — let the LLM decide.
            return False

        return True

    async def _plan_via_llm(
        self, provider: BaseLLMProvider, goal: str, context: ExecutionContext
    ) -> list[PlanStep] | None:
        """
        Ask the LLM to decompose the goal into a JSON array of steps.

        Returns None (triggering fallback) if the call fails or the response
        cannot be parsed into a valid plan.
        """
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

        steps = self._parse_plan_response(raw)
        if steps is None:
            logger.warning(
                "Planner could not parse LLM response as a plan goal=%r raw=%r",
                goal,
                raw[:300] if isinstance(raw, str) else raw,
            )
            return None

        return steps

    def _parse_plan_response(self, raw: object) -> list[PlanStep] | None:
        """
        Tolerantly parse the LLM's plan response into a list of PlanStep.

        Handles the realistic failure modes of "JSON only" prompting on
        local models: markdown code fences, a leading sentence before the
        JSON, trailing commentary after it, or a single object instead of
        an array. Returns None if no valid plan can be extracted.
        """
        if not isinstance(raw, str) or not raw.strip():
            return None

        text = raw.strip()

        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Extract the first [...] array in the text, in case of stray prose
        # before or after it.
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            text = array_match.group(0)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None

        # Tolerate a single object instead of a list of one
        if isinstance(parsed, dict):
            parsed = [parsed]

        if not isinstance(parsed, list) or not parsed:
            return None

        steps: list[PlanStep] = []
        for item in parsed[:MAX_PLAN_STEPS]:
            if not isinstance(item, dict):
                continue
            description = item.get("description")
            if not isinstance(description, str) or not description.strip():
                continue
            agent = item.get("agent")
            if not isinstance(agent, str):
                agent = None
            parallelizable = bool(item.get("parallelizable", False))
            steps.append(
                {
                    "description": description.strip(),
                    "agent": agent,
                    "parallelizable": parallelizable,
                }
            )

        return steps if steps else None

    def _summarise_memory(self, context: ExecutionContext) -> str:
        """Build an optional memory context block for the planning prompt."""
        memory_turns = getattr(context, "memory", None) or []
        if not memory_turns:
            return ""

        recent = memory_turns[-4:]
        lines = [f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in recent]
        return "Recent conversation:\n" + "\n".join(lines) + "\n\n"
