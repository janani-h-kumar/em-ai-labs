"""Dynamic dependency-aware memory factory."""

import inspect
import logging

logger = logging.getLogger(__name__)


class MemoryFactory:
    """
    Constructs memory instances using constructor introspection.

    Uses `create_dynamic` for flexible dependency injection.
    """

    def __init__(
        self,
        container,
    ):
        self.provider = container.provider
        self.tool_registry = container.tool_registry
        self.config_manager = container.config_manager

    def create(self, memory_class):
        """Create a memory instance using constructor introspection."""
        return self.create_dynamic(memory_class)

    def create_dynamic(self, memory_class):
        signature = inspect.signature(memory_class.__init__)

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
                "Unresolved dependency '%s' for memory '%s'",
                param_name,
                memory_class.__name__,
            )

        logger.info(
            "Creating memory=%s dependencies=%s",
            memory_class.__name__,
            list(kwargs.keys()),
        )

        return memory_class(**kwargs)
