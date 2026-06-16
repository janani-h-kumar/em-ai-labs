from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class HealthStatus:
    status: str  # "healthy" | "degraded" | "down"
    provider: str
    status_code: int | None = None
    error: str | None = None


class BaseLLMProvider(ABC):
    """
    Every LLM provider (Ollama, Claude, OpenAI, …) must implement this interface.
    Agents call this — never a specific provider directly.
    """

    @abstractmethod
    def chat_completion(
        self,
        messages: str | list[dict],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a prompt and return the text response.

        Args:
            messages: Either a plain string (single-turn) or a list of
                      {"role": ..., "content": ...} dicts (multi-turn).
            system_prompt: Optional system context to prepend.
            max_tokens: Optional maximum number of tokens for the model
                        response.

        Returns:
            The model's text response as a string.
        """
        ...

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Return the health status of the provider."""
        ...

    @property
    @abstractmethod
    def model_name(self):
        """The name of the currently active model."""
        ...
