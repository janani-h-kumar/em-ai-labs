from __future__ import annotations

from typing import Any

from src.guardrails import (
    GuardrailConfig,
    mark_guardrail_violation,
)
from src.guardrails.exceptions import GuardrailViolationError


class OutputGuardrail:
    """Validate outputs that must be usable by callers or the orchestrator."""

    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()

    def validate_final_response(self, response: object) -> str:
        if response is None:
            text = ""
        else:
            text = str(response).strip()

        if text:
            return text

        violation = GuardrailViolationError(
            code="output.empty_response",
            public_message="I could not produce a useful response for that request.",
        )
        mark_guardrail_violation(violation)
        raise violation

    def validate_planner_steps(self, raw: object, parsed: object) -> list[dict[str, Any]] | None:
        if parsed is None:
            self._mark_malformed(raw)
            return None

        if isinstance(parsed, dict):
            parsed = [parsed]

        if not isinstance(parsed, list) or not parsed:
            self._mark_malformed(raw)
            return None

        steps: list[dict[str, Any]] = []
        for item in parsed[: self.config.max_tasks_per_execution]:
            if not isinstance(item, dict):
                continue

            description = item.get("description")
            if not isinstance(description, str) or not description.strip():
                continue

            agent = item.get("agent")
            if not isinstance(agent, str):
                agent = None

            steps.append(
                {
                    "description": description.strip(),
                    "agent": agent,
                    "parallelizable": bool(item.get("parallelizable", False)),
                }
            )

        if not steps:
            self._mark_malformed(raw)
            return None

        return steps

    def _mark_malformed(self, raw: object) -> None:
        violation = GuardrailViolationError(
            code="output.malformed_planner_json",
            public_message="The local model returned an invalid plan, so I used a safe fallback.",
            details={"raw_type": type(raw).__name__},
        )
        mark_guardrail_violation(violation)
