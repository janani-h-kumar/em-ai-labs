from unittest.mock import MagicMock, patch

from src.runtimes.langchain_runtime import LangChainRuntime


def create_mock_config():
    config = MagicMock()

    values = {
        "llm.provider": "ollama",
        "llm.model": "llama3",
        "llm.base_url": "http://localhost:11434",
    }

    config.get.side_effect = lambda key, default=None: values.get(key, default)

    return config


@patch("src.runtimes.langchain_runtime.requests.get")
@patch("src.runtimes.langchain_runtime.ChatOllama")
def test_runtime_initializes(mock_chat_ollama, mock_get):
    mock_chat_ollama.return_value = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    runtime = LangChainRuntime(create_mock_config())

    assert runtime is not None
