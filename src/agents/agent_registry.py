"""Dynamic agent discovery and registration.

Registry discovers agent classes and stores class metadata only. Use
`create_instance` to construct an agent via the AgentFactory.
"""

import importlib
import inspect
import logging
import pkgutil
import types
from dataclasses import dataclass

from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseAgent
from src.core.container import ServiceContainer

logger = logging.getLogger(__name__)


@dataclass
class AgentDescriptor:
    """Metadata descriptor for a registered agent."""

    name: str
    description: str
    capabilities: list[str]
    agent_class: type[BaseAgent]
    version: str = "1.0"


class AgentRegistry:
    """
    Dynamically discovers and registers agent classes.

    Responsibilities:
    - Discover agent classes
    - Store descriptor metadata and class references (no instances)
    - Provide factory-backed instance creation when requested

    FIXME: Backwards compatibility: temporarily accept raw agent class entries
    when tests or older code still assign classes directly to registry.agents.
    This will be removed once the descriptor migration is complete across the
    whole codebase.
    """

    def __init__(self, container: ServiceContainer) -> None:
        self.container = container

        # maps agent_name -> descriptor or raw agent class
        self.agents: dict[str, AgentDescriptor | type[BaseAgent]] = {}

        # FIX: cache constructed instances — construct once, reuse per request
        self._instances: dict[str, BaseAgent] = {}

        self.agent_factory = AgentFactory(
            container=container,
        )

        self.discover_agents()

    def discover_agents(self) -> None:
        """Auto-discover all agent implementations and register classes."""
        import src.agents as agents_package

        logger.info("Discovering agents...")

        for _, module_name, _ in pkgutil.iter_modules(agents_package.__path__):
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

    def _register_module_agents(self, module: types.ModuleType) -> None:
        """Register BaseAgent subclasses from module (store descriptors only)."""
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
        """
        Return an agent instance by name, constructing it on first call.

        FIX: cached — second call for same name returns the same instance.
        Agents must be stateless between requests; all request state lives
        in ExecutionContext passed to handle().
        """
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found. Available: {list(self.agents)}")

        if name not in self._instances:
            descriptor_or_class = self.agents[name]
            if isinstance(descriptor_or_class, AgentDescriptor):
                agent_class = descriptor_or_class.agent_class
            else:
                agent_class = descriptor_or_class
            self._instances[name] = self.agent_factory.create(agent_class)
            logger.info("Constructed and cached agent instance: %s", name)

        return self._instances[name]

    def get(self, name: str) -> BaseAgent:
        """Return an agent instance by name (legacy compatibility alias)."""
        return self.create_instance(name)

    def get_class(self, name: str) -> type[BaseAgent]:
        """Return the agent class for the given name."""
        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")
        descriptor_or_class = self.agents[name]
        if isinstance(descriptor_or_class, AgentDescriptor):
            return descriptor_or_class.agent_class
        return descriptor_or_class

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self.agents

    def health_check(self) -> dict[str, dict]:
        """Return a lightweight health map for discovered agents.

        Avoids instantiating agents — uses descriptor metadata only.
        """
        return {
            name: {
                "status": "discovered",
                "class": descriptor.agent_class.__name__
                if isinstance(descriptor, AgentDescriptor)
                else descriptor.__name__,
                "capabilities": descriptor.capabilities
                if isinstance(descriptor, AgentDescriptor)
                else getattr(descriptor, "capabilities", []),
            }
            for name, descriptor in self.agents.items()
        }
