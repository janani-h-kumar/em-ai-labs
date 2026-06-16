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

    FIX: Instances are now cached after first construction. Before this fix,
    every call to create_instance() ran the full constructor including
    initialize() — correct for stateless agents now, but a resource leak
    the moment any agent opens a DB connection or loads a model in initialize().
    """

    def __init__(self, container):
        self.container = container

        # maps agent_name -> agent_class
        self.agents: dict[str, type[BaseAgent]] = {}

        # FIX: cache constructed instances — construct once, reuse per request
        self._instances: dict[str, BaseAgent] = {}

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
            if not issubclass(obj, BaseAgent) or obj is BaseAgent:
                continue
            try:
                agent_name = getattr(obj, "name", obj.__name__.replace("Agent", "").lower())
                self.agents[agent_name] = obj
                logger.info("Registered agent class: %s -> %s", agent_name, obj.__name__)
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
            agent_class = self.agents[name]
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
        return self.agents[name]

    def list_agents(self) -> list[str]:
        return list(self.agents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self.agents

    def health_check(self) -> dict[str, dict]:
        """Return a lightweight health map for discovered agents.

        Avoids instantiating agents — uses class metadata only.
        """
        return {
            name: {"status": "discovered", "class": cls.__name__}
            for name, cls in self.agents.items()
        }
