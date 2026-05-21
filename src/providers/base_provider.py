from abc import ABC, abstractmethod
from typing import Union

class BaseLLMProvider(ABC):
    """
    Every LLM provider (Ollama, Claude, OpenAI, …) must implement this interface.
    Agents call this — never a specific provider directly.
    """

    @abstractmethod
    def chat_completion(
        self,
        messages: Union[str, list[dict]],
        system_prompt: str | None = None,
    ) -> str:
        """
        Send a prompt and return the text response.

        Args:
            messages: Either a plain string (single-turn) or a list of
                      {"role": ..., "content": ...} dicts (multi-turn).
            system_prompt: Optional system context to prepend.

        Returns:
            The model's text response as a string.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable and a model is available."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The name of the currently active model."""
        ...