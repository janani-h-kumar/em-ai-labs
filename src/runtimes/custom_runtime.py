"""
Placeholder for the custom orchestration runtime.

This runtime is a Phase 2 implementation target and is intentionally
not yet functional. It exists to reserve the runtime switch path and
provide a clear message if selected in config.
"""

import logging
from typing import Any

from src.runtimes.base_runtime import BaseRuntime

logger = logging.getLogger(__name__)


class CustomRuntimeNotImplementedError(Exception):
    """Raised when custom runtime is selected but not implemented."""
    pass


class CustomRuntime(BaseRuntime):
    """
    Custom rule-based runtime placeholder.
    """

    def __init__(self, config_manager: object | None = None):
        super().__init__(name="CustomRuntime")
        logger.info("CustomRuntime placeholder initialized")

    def invoke(self, message: str) -> str:
        raise CustomRuntimeNotImplementedError(
            "Custom runtime is not yet implemented. "
            "Please set runtime.orchestration to 'langchain' in configs/config.yaml."
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime": self.name,
            "status": "not_implemented",
            "message": "Custom runtime is not implemented yet."
        }
