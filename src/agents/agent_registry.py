"""Dynamic agent discovery and registration."""

import importlib
import inspect
import logging
import pkgutil
import types

from src.agents.agent_descriptor import AgentDescriptor
from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseAgent
from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Dynamically discovers and registers agent classes.

    Stores AgentDescriptor objects only — no raw agent classes, no instances.
    Instances are cached after first construction by create_instance().
    """

    def __init__(self, container: ServiceContainer) -> None:
        self.container = container
        # maps agent_name -> AgentDescriptor (descriptor-only, no raw classes)
        self.agents: dict[str, AgentDescriptor] = {}
        # cached instances — construct once, reuse per request
        self._instances: dict[str, BaseAgent] = {}
        self.agent_factory = AgentFactory(container=container)
        self.discover_agents()

    def discover_agents(self) -> None:
        """Auto-discover all agent implementations and register descriptors."""
        import src.agents as agents_package

        logger.info("Discovering agents...")

        for _, module_name, _ in pkgutil.iter_modules(agents_package.__path__):
            if module_name in {"base_agent", "agent_factory", "agent_registry"}:
                continue

            full_module_name = f"src.agents.{module_name}"
            try:
                logger.info("Importing agent module: %s", full_module_name)
                module = importlib.import_module(full_module_name)
                self._register_module_agents(module)
            except Exception:
                logger.exception("Failed to import agent module: %s", full_module_name)

        logger.info("Registered agent classes: %s", list(self.agents.keys()))

    def _register_module_agents(self, module: types.ModuleType) -> None:
        """Register BaseAgent subclasses from module as AgentDescriptors."""
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseAgent) or obj is BaseAgent:
                continue
            try:
                agent_name = getattr(obj, "name", obj.__name__.replace("Agent", "").lower())
                descriptor = AgentDescriptor(
                    name=agent_name,
                    description=getattr(obj, "description", ""),
                    capabilities=getattr(obj, "capabilities", []) or [],
                    agent_class=obj,
                )
                self.agents[agent_name] = descriptor
                logger.info("Registered agent descriptor: %s -> %s", agent_name, obj.__name__)
            except Exception:
                logger.exception("Failed to register agent class: %s", obj.__name__)

    def create_instance(self, name: str) -> BaseAgent:
        """Return an agent instance by name, constructing on first call."""
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found. Available: {list(self.agents)}")

        if name not in self._instances:
            self._instances[name] = self.agent_factory.create(self.agents[name].agent_class)
            logger.info("Constructed and cached agent instance: %s", name)

        return self._instances[name]

    def get(self, name: str) -> BaseAgent:
        """Alias for create_instance (legacy compatibility)."""
        return self.create_instance(name)

    def get_class(self, name: str) -> type[BaseAgent]:
        """Return the agent class for the given name."""
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")
        return self.agents[name].agent_class

    def descriptors(self) -> list[AgentDescriptor]:
        """Return all AgentDescriptors — use this to build the router."""
        return list(self.agents.values())

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self.agents

    def health_check(self) -> dict[str, dict]:
        """Lightweight health map using descriptor metadata only."""
        return {
            name: {
                "status": "discovered",
                "class": d.agent_class.__name__,
                "capabilities": d.capabilities,
                "version": d.version,
            }
            for name, d in self.agents.items()
        }
