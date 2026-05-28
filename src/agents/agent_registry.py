"""
Dynamic agent discovery and registration.
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
    Dynamically discovers and registers agents.

    Responsibilities:
    - Discover agent classes
    - Instantiate agents via AgentFactory
    - Store initialized agent instances
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        self.agents = {}

        self.agent_factory = AgentFactory(
            config_manager=container.config_manager,
            provider=container.provider,
            tool_registry=container.tool_registry,
        )

        self.discover_agents()

    def discover_agents(self):
        """
        Auto-discover all agent implementations.
        """

        import src.agents as agents_package

        logger.info("Discovering agents...")

        for _, module_name, _ in pkgutil.iter_modules(agents_package.__path__):
            # -------------------------------------------------
            # Skip framework/internal modules
            # -------------------------------------------------

            if module_name in [
                "base_agent",
                "agent_factory",
                "agent_registry",
            ]:
                continue

            full_module_name = f"src.agents.{module_name}"

            try:
                logger.info(
                    "Importing agent module: %s",
                    full_module_name,
                )

                module = importlib.import_module(full_module_name)

                self._register_module_agents(module)

            except Exception:
                logger.exception(
                    "Failed to import agent module: %s",
                    full_module_name,
                )

        logger.info(
            "Registered agents: %s",
            list(self.agents.keys()),
        )

    def _register_module_agents(
        self,
        module,
    ):
        """
        Register BaseAgent subclasses from module.
        """

        for _, obj in inspect.getmembers(
            module,
            inspect.isclass,
        ):
            # -------------------------------------------------
            # Must inherit BaseAgent
            # -------------------------------------------------

            if not issubclass(
                obj,
                BaseAgent,
            ):
                continue

            # -------------------------------------------------
            # Skip abstract base
            # -------------------------------------------------

            if obj is BaseAgent:
                continue

            try:
                logger.info(
                    "Creating agent instance: %s",
                    obj.__name__,
                )

                # ---------------------------------------------
                # Create via factory
                # ---------------------------------------------

                agent_instance = self.agent_factory.create(obj)

                # ---------------------------------------------
                # Agent naming
                # ---------------------------------------------

                agent_name = getattr(
                    agent_instance,
                    "name",
                    obj.__name__.replace(
                        "Agent",
                        "",
                    ).lower(),
                )

                self.agents[agent_name] = agent_instance

                logger.info(
                    "Registered agent: %s",
                    agent_name,
                )

            except Exception as e:
                logger.exception(
                    "Failed to register agent class: %s with error: %s",
                    obj.__name__,
                    str(e),
                )

    def get(
        self,
        name: str,
    ):
        """
        Retrieve agent by name.
        """

        if name not in self.agents:
            raise ValueError(f"Agent '{name}' not found.")

        return self.agents[name]

    def list_agents(self):
        """
        Return all registered agents.
        """

        return list(self.agents.keys())

    def has_agent(
        self,
        name: str,
    ) -> bool:
        """
        Check whether agent exists.
        """

        return name in self.agents
