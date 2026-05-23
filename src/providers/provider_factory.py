from src.providers.base_provider import BaseLLMProvider
from src.providers.claude_provider import ClaudeProvider
from src.providers.ollama_provider import OllamaClient


class ProviderFactory:
    """
    Factory class responsible for creating configured LLM providers.
    """

    @staticmethod
    def get_provider(config_manager) -> BaseLLMProvider:
        """
        Returns the provider specified in config.yaml under `llm.provider`.

        Supported providers:
        - ollama
        - claude

        Defaults to 'ollama' for backward compatibility.
        """
        provider = config_manager.get("llm.provider", "ollama")

        if provider == "ollama":
            return OllamaClient(config_manager)

        if provider == "claude":
            return ClaudeProvider(config_manager)

        raise ValueError(f"Unknown provider: {provider}. Choose 'ollama' or 'claude'.")


def get_provider(config_manager) -> BaseLLMProvider:
    """
    Backward-compatible helper function.
    Existing code importing get_provider() will continue to work.
    """
    return ProviderFactory.get_provider(config_manager)
