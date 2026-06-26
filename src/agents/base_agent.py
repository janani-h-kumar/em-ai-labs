"""
BaseAgent — abstract base class for all em-ai-labs agents.

Design contract:
- Config, provider, and tools are INJECTED from outside — never created internally.
- Every subclass must implement initialize() and handle().
- Structured logging via logging_utils is set up at the entrypoint (main.py);
  agents just call logger.getLogger(__name__) — the JSON formatter is already active.
- health_check() is provided here; subclasses may override to add domain checks.
- _build_messages() is provided here; subclasses use it to make every LLM call
  memory-aware without each agent re-implementing context injection.

Architectural Rule:

Agents are stateless services.

Do not store:
    self.session_id
    self.current_user
    self.history
    self.last_result

Store only:
    injected dependencies
    prompts
    configuration

Request state belongs in ExecutionContext.
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
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
    - _build_messages() for memory-aware LLM calls (see Pillar 1 below).

    Usage:
        class WeatherAgent(BaseAgent):

            def initialize(self) -> None:
                self.weather_tool = WeatherTool(self.config_manager)
                self.provider = get_provider(self.config_manager)

            async def handle(self, task, context) -> str:
                city = self.extract_city(task.description)
                messages = self._build_messages(task, context)
                return self.base_llm_provider.chat_completion(
                    messages, system_prompt=self.system_prompt
                )

    Why config_manager is injected (not a path string):
        Passing a path string forces the base class to know about the
        filesystem layout and creates a new ConfigManager per agent.
        Injecting a shared ConfigManager means one load, one source of
        truth, and trivial testing (just pass a mock).

    Memory injection contract [Pillar 1]:
        ExecutionContext.memory is a list[dict] of {"role", "content"} turns,
        already in the shape BaseLLMProvider.chat_completion() expects for its
        `messages` parameter. Before this change, context.memory was built by
        the Orchestrator but no agent ever read it — every LLM call used only
        task.description, discarding conversation history.

        _build_messages() closes that gap once, here, so every current and
        future agent is memory-aware automatically — no per-agent wiring.
    """

    # Metadata contract (subclasses should override)
    name: str = ""
    description: str = ""
    capabilities: list[str] | None = None

    # Number of most-recent memory turns to inject into every LLM call.
    # Override per-agent if a domain needs more or less context.
    memory_window: int = 6

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Initialise the agent with an already-constructed ConfigManager.

        Args:
            config_manager: Fully loaded ConfigManager instance.
                            Build it once in main.py / ApplicationService and
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
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _build_messages(
        self,
        task: Any,
        context: Any,
        extra_content: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Build a memory-aware message list for BaseLLMProvider.chat_completion().

        [Pillar 1] This is the single place context injection happens. Every
        agent calls this instead of passing task.description directly, so
        conversation history flows into every LLM call without each agent
        re-implementing the same plumbing.

        Args:
            task: Task with .description — the current request.
            context: ExecutionContext with .memory — a list[dict] of prior
                     {"role", "content"} turns. May be None or empty;
                     handled gracefully either way.
            extra_content: Optional additional content to use in place of
                     task.description (e.g. a pre-formatted prompt with
                     tool results already interpolated, as WeatherAgent does).

        Returns:
            list[dict[str, str]] in the shape BaseLLMProvider.chat_completion()
            expects: [{"role": "user"|"assistant", "content": "..."}].
            Memory turns come first (oldest to newest), current task last.

        Example:
            messages = self._build_messages(task, context)
            # [
            #   {"role": "human", "content": "What's the weather in Seattle?"},
            #   {"role": "ai", "content": "Seattle is 52°F with light rain."},
            #   {"role": "user", "content": "What about tomorrow?"},
            # ]
            response = self.base_llm_provider.chat_completion(
                messages, system_prompt=self.system_prompt
            )
        """
        messages: list[dict[str, str]] = []

        memory_turns = getattr(context, "memory", None) or []
        if memory_turns:
            window = memory_turns[-self.memory_window :]
            for turn in window:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        current_content = (
            extra_content if extra_content is not None else getattr(task, "description", "")
        )
        messages.append({"role": "user", "content": current_content})

        return messages
