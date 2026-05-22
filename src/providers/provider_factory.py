from src.providers.base_provider import BaseLLMProvider
from src.providers.claude_provider import ClaudeProvider
from src.providers.ollama_provider import OllamaClient


def get_provider(config_manager) -> BaseLLMProvider:
    """
    Returns the provider specified in config.yaml under `llm.provider`.
    Defaults to 'ollama' so existing setups keep working.
    """
    provider = config_manager.get("llm.provider", "ollama")

    if provider == "ollama":
        return OllamaClient(config_manager)
    elif provider == "claude":
        return ClaudeProvider(config_manager)
    else:
        raise ValueError(f"Unknown provider: {provider}. Choose 'ollama' or 'claude'.")
