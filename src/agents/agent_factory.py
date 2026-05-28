"""
Dynamic dependency-aware agent factory.
"""

import inspect
import logging

from src.agents.weather_agent import WeatherAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Constructs agents using constructor introspection.

    """

    def __init__(
        self,
        config_manager,
        provider,
        tool_registry,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.config_manager = (
            config_manager  # ConfigManager can be injected if needed in the future
        )

    def create(
        self,
        agent_class,
    ):
        return WeatherAgent(
            config_manager=self.config_manager,
            base_llm_provider=self.provider,
            weather_tool=self.tool_registry.get_tool("weather_tool"),
        )

    def create_dynamic(
        self,
        agent_class,
    ):
        signature = inspect.signature(agent_class.__init__)

        kwargs = {}

        # dynamic creation can be resumed later. For now we only have one agent and we want to keep it simple.
        for param_name in signature.parameters:
            # -----------------------------------------
            # Skip self
            # -----------------------------------------

            if param_name == "self":
                continue

            # -----------------------------------------
            # ConfigManager
            # -----------------------------------------

            if param_name == "config_manager":
                kwargs[param_name] = self.container.config_manager

                continue

            # -----------------------------------------
            # Base LLM Provider
            # -----------------------------------------

            if param_name == "base_llm_provider":
                kwargs[param_name] = self.container.provider

                continue

            # -----------------------------------------
            # Tool Injection
            # -----------------------------------------

            tool = self.container.tool_registry.get_tool(param_name)

            if tool:
                kwargs[param_name] = tool

                continue

            # -----------------------------------------
            # Unknown dependency
            # -----------------------------------------

            logger.warning(
                "Unresolved dependency '%s' for agent '%s'",
                param_name,
                agent_class.__name__,
            )

        logger.info(
            "Creating agent=%s dependencies=%s",
            agent_class.__name__,
            list(kwargs.keys()),
        )

        return agent_class(**kwargs)
