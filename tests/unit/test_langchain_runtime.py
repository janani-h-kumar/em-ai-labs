from unittest.mock import MagicMock, patch

from src.runtimes.langchain_runtime import LangChainRuntime


def create_mock_config():
    config = MagicMock()

    config_values = {
        "llm.provider": "ollama",
        "llm.model": "llama3",
        "llm.base_url": "http://localhost:11434",
    }

    config.get.side_effect = lambda key, default=None: config_values.get(key, default)

    return config


@patch("src.runtimes.langchain_runtime.ChatOllama")
def test_runtime_initializes(mock_chat_ollama):
    mock_chat_ollama.return_value = MagicMock()

    config = create_mock_config()

    runtime = LangChainRuntime(config)

    assert runtime is not None


@patch("src.runtimes.langchain_runtime.ChatOllama")
def test_runtime_has_config(mock_chat_ollama):
    mock_chat_ollama.return_value = MagicMock()

    config = create_mock_config()

    runtime = LangChainRuntime(config)

    assert runtime.config_manager == config
