"""Dynamic agent discovery and registration.

Registry discovers agent classes and stores class metadata only. Use
`create_instance` to construct an agent via the AgentFactory.
"""

import importlib
import inspect
import logging
import pkgutil

from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Dynamically discovers and registers agent classes.

    Responsibilities:
    - Discover agent classes
    - Store class references and metadata (no instances)
    - Provide factory-backed instance creation when requested
    """

    def __init__(self, container):
        self.container = container

        # maps agent_name -> agent_class
        self.agents: dict[str, type[BaseAgent]] = {}

        self.agent_factory = AgentFactory(
            config_manager=container.config_manager,
            provider=container.provider,
            tool_registry=container.tool_registry,
        )

        self.discover_agents()

    def discover_agents(self):
        """Auto-discover all agent implementations and register classes."""

        import src.agents as agents_package

        logger.info("Discovering agents...")

        for _, module_name, _ in pkgutil.iter_modules(agents_package.__path__):
            # skip framework/internal modules
            if module_name in ["base_agent", "agent_factory", "agent_registry"]:
                continue

            full_module_name = f"src.agents.{module_name}"

            try:
                logger.info("Importing agent module: %s", full_module_name)

                module = importlib.import_module(full_module_name)

                self._register_module_agents(module)

            except Exception:
                logger.exception("Failed to import agent module: %s", full_module_name)

        logger.info("Registered agent classes: %s", list(self.agents.keys()))

    def _register_module_agents(self, module):
        """Register BaseAgent subclasses from module (store classes only)."""

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseAgent):
                continue

            if obj is BaseAgent:
                continue

            try:
                logger.info("Discovered agent class: %s", obj.__name__)

                # Prefer class-level `name` attribute; fall back to class name
                agent_name = getattr(obj, "name", obj.__name__.replace("Agent", "").lower())

                self.agents[agent_name] = obj

                logger.info("Registered agent class: %s -> %s", agent_name, obj.__name__)

            except Exception:
                logger.exception("Failed to register agent class: %s", obj.__name__)

    def create_instance(self, name: str):
        """Construct an agent instance by name using the AgentFactory."""
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")

        agent_class = self.agents[name]
        return self.agent_factory.create(agent_class)

    def get(self, name: str):
        """Return an agent instance by name (legacy compatibility)."""
        return self.create_instance(name)

    def get_class(self, name: str):
        """Return the agent class for the given name."""
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")

        return self.agents[name]

    def list_agents(self):
        return list(self.agents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self.agents

    def health_check(self) -> dict[str, dict]:
        """Return a lightweight health map for discovered agents.

        This avoids instantiating agents (which may call external services).
        """
        out: dict[str, dict] = {}

        for name, cls in self.agents.items():
            out[name] = {
                "status": "discovered",
                "class": cls.__name__,
            }

        return out
