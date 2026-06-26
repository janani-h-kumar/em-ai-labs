from typing import Any


class GuardrailViolationError(Exception):
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
