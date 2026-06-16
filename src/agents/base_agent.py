"""
BaseAgent — abstract base class for all em-ai-labs agents.

Design contract:
- Config, provider, and tools are INJECTED from outside — never created internally.
- Every subclass must implement initialize() and handle().
- Structured logging via logging_utils is set up at the entrypoint (main.py);
  agents just call logger.getLogger(__name__) — the JSON formatter is already active.
- health_check() is provided here; subclasses may override to add domain checks.
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime  # FIX: import UTC alongside datetime
from typing import Any

from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class AgentError(Exception):
    """Base exception for all agent failures."""


class AgentInitError(AgentError):
    """Raised when an agent fails to initialise."""


class AgentExecutionError(AgentError):
    """Raised when an agent fails during execution."""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """
    Abstract base class every agent in this harness must inherit from.

    Enforces:
    - Dependency injection: ConfigManager is passed in, never created internally.
    - initialize() lifecycle hook called once at construction — set up your
      API clients, prompts, and tool references here.
    - handle() entrypoint — the router and orchestrator always call this.
    - Structured logging at init and on failure.
    - health_check() for monitoring and smoke-testing.

    Usage:
        class WeatherAgent(BaseAgent):

            def initialize(self) -> None:
                self.weather_tool = WeatherTool(self.config_manager)
                self.provider = get_provider(self.config_manager)

            async def handle(self, task, context) -> str:
                city = self.extract_city(task.description)
                return await self.get_weather_summary(city)

    Why config_manager is injected (not a path string):
        Passing a path string forces the base class to know about the
        filesystem layout and creates a new ConfigManager per agent.
        Injecting a shared ConfigManager means one load, one source of
        truth, and trivial testing (just pass a mock).
    """

    # Metadata contract (subclasses should override)
    name: str = ""
    description: str = ""
    capabilities: list[str] | None = None

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialise the agent with an already-constructed ConfigManager.

        Args:
            config_manager: Fully loaded ConfigManager instance.
                            Build it once in main.py / AgentManager and
                            pass it to every agent that needs it.

        Raises:
            AgentInitError: If initialize() raises for any reason.
        """
        self.config_manager: ConfigManager = config_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized: bool = False

        try:
            self.initialize()
            self._initialized = True
            self.logger.info("Agent initialised name=%s", self.__class__.__name__)
            if not getattr(self, "name", "") or not getattr(self, "capabilities", None):
                self.logger.warning(
                    "Agent %s missing metadata (name/capabilities).",
                    self.__class__.__name__,
                )
        except AgentInitError:
            raise
        except Exception as e:
            self.logger.exception(
                "Failed to initialise agent name=%s: %s",
                self.__class__.__name__,
                e,
            )
            raise AgentInitError(f"Failed to initialise {self.__class__.__name__}: {e}") from e

    # -----------------------------------------------------------------------
    # Abstract interface — subclasses MUST implement both
    # -----------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> None:
        """
        Set up API clients, tools, prompts, and any domain-specific state.

        Called once by __init__. Do NOT call super().initialize().
        Raise AgentInitError if a required dependency is unavailable.
        """

    @abstractmethod
    async def handle(self, task: Any, context: Any) -> str:
        """
        Process a task and return a response string.

        This is the single entrypoint the router and orchestrator call.
        All domain logic lives here or in private methods called from here.

        Args:
            task: Task dataclass with .description and .id.
            context: ExecutionContext with .session_id, .goal, .memory.

        Returns:
            Response string. Never None.
        """

    # -----------------------------------------------------------------------
    # Concrete helpers — available to all subclasses
    # -----------------------------------------------------------------------

    def is_initialized(self) -> bool:
        """Return True if initialize() completed without error."""
        return self._initialized

    def get_config(self, key: str, default: Any | None = None) -> Any | None:
        """
        Convenience wrapper for config access with dot notation.

        Args:
            key: Dot-notation config key, e.g. 'env.OPENWEATHER_API_KEY'
            default: Value to return if key is absent.
        """
        return self.config_manager.get(key, default)

    def health_check(self) -> dict[str, Any]:
        """
        Return a health status dict for monitoring and smoke-testing.

        Subclasses should override to add domain-specific checks.
        """
        return {
            "agent": self.__class__.__name__,
            "status": "healthy" if self._initialized else "unhealthy",
            "initialized": self._initialized,
            "timestamp": datetime.now(UTC).isoformat(),  # FIX: utcnow() deprecated in 3.12
        }
