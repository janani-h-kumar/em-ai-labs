"""Dynamic dependency-aware agent factory."""

import inspect
import logging

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Constructs agents using constructor introspection.

    Uses `create_dynamic` for flexible dependency injection.
    """

    def __init__(
        self,
        container,
    ):
        self.provider = container.provider
        self.tool_registry = container.tool_registry
        self.config_manager = container.config_manager

    def create(self, agent_class):
        """Create an agent instance using constructor introspection."""
        return self.create_dynamic(agent_class)

    def create_dynamic(self, agent_class):
        signature = inspect.signature(agent_class.__init__)

        kwargs = {}

        for param_name in signature.parameters:
            if param_name == "self":
                continue

            if param_name == "config_manager":
                kwargs[param_name] = self.config_manager
                continue

            if param_name == "base_llm_provider":
                kwargs[param_name] = self.provider
                continue

            # Tool Injection by parameter name
            tool = self.tool_registry.get_tool(param_name)

            if tool:
                kwargs[param_name] = tool
                continue

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
