"""
Application dependency container.
"""

from src.memory.memory_factory import MemoryFactory
from src.memory.memory_registry import MemoryRegistry
from src.providers.provider_factory import (
    ProviderFactory,
)
from src.tools.tool_registry import (
    ToolRegistry,
)


class ServiceContainer:
    def __init__(
        self,
        config_manager,
    ):

        self.config_manager = config_manager

        # -----------------------------------------
        # Providers
        # -----------------------------------------

        self.provider = ProviderFactory.get_provider(config_manager)

        # -----------------------------------------
        # Tools
        # -----------------------------------------

        self.tool_registry = ToolRegistry(config_manager)

        self.tool_registry.discover_tools()

        # -----------------------------------------
        # Memory
        # -----------------------------------------
        self.memory_registry = MemoryRegistry()
        self.memory_factory = MemoryFactory(self)

        memory_backend_name = config_manager.get(
            "memory.backend",
            config_manager.get("persistence.type", "memory"),
        )

        if not memory_backend_name:
            memory_backend_name = "memory"

        if not self.memory_registry.has_backend(memory_backend_name):
            raise ValueError(
                "Unknown memory backend: %s. Available backends: %s"
                % (
                    memory_backend_name,
                    self.memory_registry.list_backends(),
                )
            )

        memory_class = self.memory_registry.get_class(memory_backend_name)
        self.memory = self.memory_factory.create(memory_class)
