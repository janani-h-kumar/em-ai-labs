"""Dynamic dependency-aware agent factory."""

from __future__ import annotations

import inspect
import logging

logger = logging.getLogger(__name__)


class AgentDependencyError(RuntimeError):
    """Raised when a required agent constructor dependency cannot be resolved."""


class AgentFactory:
    """Construct agents from dependencies owned by the service container."""

    def __init__(self, container) -> None:
        self.provider = container.provider
        self.tool_registry = container.tool_registry
        self.config_manager = container.config_manager

    def create(self, agent_class):
        return self.create_dynamic(agent_class)

    def create_dynamic(self, agent_class):
        signature = inspect.signature(agent_class.__init__)
        kwargs = {}
        missing: list[str] = []

        for param_name, parameter in signature.parameters.items():
            if param_name == "self":
                continue

            if parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            dependency = self._resolve_dependency(param_name)
            if dependency is not None:
                kwargs[param_name] = dependency
                continue

            if parameter.default is inspect.Parameter.empty:
                missing.append(param_name)

        if missing:
            available_tools = sorted(
                getattr(tool, "name", name)
                for name, tool in getattr(self.tool_registry, "_tool_instances", {}).items()
            )
            message = (
                f"Unable to construct agent '{agent_class.__name__}'. "
                f"Missing required dependencies: {', '.join(missing)}. "
                f"Available tools: {available_tools}"
            )
            logger.error(message)
            raise AgentDependencyError(message)

        logger.info(
            "Creating agent=%s dependencies=%s",
            agent_class.__name__,
            list(kwargs.keys()),
        )
        return agent_class(**kwargs)

    def _resolve_dependency(self, param_name: str):
        if param_name == "config_manager":
            return self.config_manager
        if param_name == "base_llm_provider":
            return self.provider
        return self.tool_registry.get_tool(param_name)
