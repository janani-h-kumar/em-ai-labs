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
from datetime import datetime
from typing import Any, Dict, Optional

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
                self.weather_client = WeatherTool(self.config_manager)
                self.provider = get_provider(self.config_manager)

            def handle(self, message: str) -> str:
                city = self.extract_city(message)
                return self.get_weather_summary(city)

    Why config_manager is injected (not a path string):
        Passing a path string forces the base class to know about the
        filesystem layout and creates a new ConfigManager per agent.
        Injecting a shared ConfigManager means one load, one source of
        truth, and trivial testing (just pass a mock).
    """

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
        # Store before initialize() so subclasses can use self.config_manager there
        self.config_manager: ConfigManager = config_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._initialized: bool = False

        try:
            self.initialize()
            self._initialized = True
            self.logger.info(
                "Agent initialised name=%s", self.__class__.__name__
            )
        except AgentInitError:
            # Already a typed error — let it propagate as-is
            raise
        except Exception as e:
            self.logger.error(
                "Failed to initialise agent name=%s error=%s",
                self.__class__.__name__, e,
                exc_info=True,
            )
            raise AgentInitError(
                f"Failed to initialise {self.__class__.__name__}: {e}"
            ) from e

    # -----------------------------------------------------------------------
    # Abstract interface — subclasses MUST implement both
    # -----------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> None:
        """
        Set up API clients, tools, prompts, and any domain-specific state.

        Called once by __init__. Do NOT call super().initialize() — there
        is no parent implementation.

        Raise AgentInitError if a required dependency is unavailable.
        Do NOT raise generic Exception — the base class wraps anything
        that isn't already an AgentInitError.

        Example:
            def initialize(self) -> None:
                self.weather_client = WeatherTool(self.config_manager)
                self.provider = get_provider(self.config_manager)
                self.system_prompt = "You are a friendly weather assistant."
        """

    @abstractmethod
    def handle(self, message: str) -> str:
        """
        Process a user message and return a response string.

        This is the single entrypoint the router and orchestrator call.
        All domain logic lives here or in private methods called from here.

        Args:
            message: Raw user input string. Never empty (router filters blanks).

        Returns:
            Response string. Never None, never raise from this method —
            catch internally and return a user-facing error string if needed.

        Example:
            def handle(self, message: str) -> str:
                try:
                    city = self.extract_city(message)
                    return self.get_weather_summary(city)
                except WeatherAgentExecutionError as e:
                    return f"Sorry, I couldn't get the weather: {e}"
        """

    # -----------------------------------------------------------------------
    # Concrete helpers — available to all subclasses
    # -----------------------------------------------------------------------

    def is_initialized(self) -> bool:
        """Return True if initialize() completed without error."""
        return self._initialized

    def get_config(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Convenience wrapper for config access with dot notation.

        Prefer calling self.config_manager.get() directly in complex cases;
        this shorthand is for simple one-liners in initialize().

        Args:
            key: Dot-notation config key, e.g. 'env.OPENWEATHER_API_KEY'
            default: Value to return if key is absent.

        Returns:
            Config value or default.
        """
        return self.config_manager.get(key, default)

    def health_check(self) -> Dict[str, Any]:
        """
        Return a health status dict for monitoring and smoke-testing.

        Subclasses should override this to add domain-specific checks,
        e.g. pinging the LLM provider or the external API.

        Returns:
            Dict with at minimum: agent, status, initialized, timestamp.

        Example override:
            def health_check(self) -> Dict[str, Any]:
                base = super().health_check()
                base["provider"] = self.provider.health_check()
                return base
        """
        return {
            "agent": self.__class__.__name__,
            "status": "healthy" if self._initialized else "unhealthy",
            "initialized": self._initialized,
            "timestamp": datetime.utcnow().isoformat(),
        }