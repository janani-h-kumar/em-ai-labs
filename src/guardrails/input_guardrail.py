from __future__ import annotations

from src.guardrails import GuardrailConfig, GuardrailViolation, mark_guardrail_violation


class InputGuardrail:
    """Validate user input before orchestration starts."""

    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()

    def validate_prompt(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            violation = GuardrailViolation(
                code="input.empty_prompt",
                public_message="Please enter a prompt so I know what to help with.",
            )
            mark_guardrail_violation(violation)
            raise violation

        stripped = prompt.strip()
        if len(stripped) > self.config.max_prompt_chars:
            violation = GuardrailViolation(
                code="input.prompt_too_long",
                public_message=(
                    "That prompt is too long for this local run. Please shorten it and try again."
                ),
                details={
                    "limit": self.config.max_prompt_chars,
                    "actual_length": len(stripped),
                },
            )
            mark_guardrail_violation(violation, limit=self.config.max_prompt_chars)
            raise violation

        return stripped
