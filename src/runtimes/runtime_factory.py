"""
Factory for creating runtime instances based on configuration.

This module provides a factory pattern for instantiating the appropriate
runtime (LangChain, custom, etc.) based on configuration settings.
"""

import logging
from typing import Any, Literal

from src.runtimes.base_runtime import BaseRuntime
from src.runtimes.langchain_runtime import LangChainRuntime
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


RuntimeType = Literal["langchain", "custom"]


class RuntimeFactory:
    """
    Factory for creating runtime instances based on configuration.

    Enables config-driven runtime selection, allowing easy switching
    between different orchestration strategies.

    Example:
        config = ConfigManager("configs/config.yaml")
        runtime_type = config.get("runtime.orchestration")  # "langchain"
        runtime = RuntimeFactory.create(runtime_type, config, tools)
    """

    @staticmethod
    def create(
        runtime_type: RuntimeType, config_manager: ConfigManager, tools: list[Any] | None = None
    ) -> BaseRuntime:
        """
        Create runtime instance based on type.

        Args:
            runtime_type: "langchain" or "custom"
            config_manager: Configuration manager instance
            tools: Optional list of Tool objects

        Returns:
            BaseRuntime subclass instance

        Raises:
            ValueError: If runtime type is unknown or initialization fails
            NotImplementedError: If runtime not yet implemented (e.g., custom)

        Example:
            runtime = RuntimeFactory.create(
                runtime_type="langchain",
                config_manager=config,
                tools=tool_list
            )
        """
        runtime_type = runtime_type.lower().strip()

        if runtime_type == "langchain":
            logger.info("Creating LangChainRuntime...")
            return LangChainRuntime(config_manager, tools)

        elif runtime_type == "custom":
            error_msg = (
                "Custom runtime not yet implemented (Phase 2). "
                "Set runtime.orchestration: 'langchain' in config.yaml for now."
            )
            logger.error(error_msg)
            raise NotImplementedError(error_msg)

        else:
            raise ValueError(
                f"Unknown runtime type: {runtime_type}. " f"Valid options: 'langchain', 'custom'"
            )
