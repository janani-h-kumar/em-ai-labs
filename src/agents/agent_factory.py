"""
Dynamic dependency-aware agent factory.
"""

import inspect
import logging

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Dynamically constructs agents using constructor introspection.

    Responsibilities:
    - Resolve dependencies from ServiceContainer
    - Inject only required dependencies
    - Avoid hardcoded agent wiring
    """

    def __init__(
        self,
        container,
    ):
        self.container = container

    def create(
        self,
        agent_class,
    ):
        """
        Dynamically construct an agent instance.

        Uses constructor parameter names to resolve
        dependencies from the container.
        """

        signature = inspect.signature(agent_class.__init__)

        kwargs = {}

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
