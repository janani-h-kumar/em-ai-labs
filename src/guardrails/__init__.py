"""
Lightweight execution guardrails for the local LLM harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentelemetry import trace


@dataclass(frozen=True)
class GuardrailConfig:
    max_prompt_chars: int = 8000
    max_react_iterations: int = 5
    max_tasks_per_execution: int = 3
    max_execution_seconds: int = 60


class GuardrailViolation(Exception):
    """Raised when a known guardrail prevents unsafe execution."""

    def __init__(
        self,
        code: str,
        public_message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.public_message = public_message
        self.details = details or {}
        super().__init__(f"{code}: {public_message}")


def load_guardrail_config(config_manager: Any | None = None) -> GuardrailConfig:
    """Load guardrail limits from YAML with env overrides."""

    defaults = GuardrailConfig()
    if config_manager is None:
        return defaults

    return GuardrailConfig(
        max_prompt_chars=_get_int(
            config_manager,
            "guardrails.max_prompt_chars",
            "env.GUARDRAILS_MAX_PROMPT_CHARS",
            defaults.max_prompt_chars,
        ),
        max_react_iterations=_get_int(
            config_manager,
            "guardrails.max_react_iterations",
            "env.GUARDRAILS_MAX_REACT_ITERATIONS",
            defaults.max_react_iterations,
        ),
        max_tasks_per_execution=_get_int(
            config_manager,
            "guardrails.max_tasks_per_execution",
            "env.GUARDRAILS_MAX_TASKS_PER_EXECUTION",
            defaults.max_tasks_per_execution,
        ),
        max_execution_seconds=_get_int(
            config_manager,
            "guardrails.max_execution_seconds",
            "env.GUARDRAILS_MAX_EXECUTION_SECONDS",
            defaults.max_execution_seconds,
        ),
    )


def mark_guardrail_violation(
    violation: GuardrailViolation,
    limit: int | float | None = None,
) -> None:
    """Annotate the active span with guardrail metadata when tracing is enabled."""

    span = trace.get_current_span()
    if not span or not span.get_span_context().is_valid:
        return

    span.set_attribute("guardrail.triggered", True)
    span.set_attribute("guardrail.code", violation.code)
    if limit is not None:
        span.set_attribute("guardrail.limit", limit)


def _get_int(
    config_manager: Any,
    yaml_key: str,
    env_key: str,
    default: int,
) -> int:
    raw_value = config_manager.get(env_key)
    if raw_value is None:
        raw_value = config_manager.get(yaml_key, default)

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


from src.guardrails.execution_guardrail import ExecutionGuardrail
from src.guardrails.input_guardrail import InputGuardrail
from src.guardrails.output_guardrail import OutputGuardrail

__all__ = [
    "ExecutionGuardrail",
    "GuardrailConfig",
    "GuardrailViolation",
    "InputGuardrail",
    "OutputGuardrail",
    "load_guardrail_config",
    "mark_guardrail_violation",
]
