"""
Application dependency container.
"""

from src.memory import InProcessMemory
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
        self.memory = InProcessMemory()
