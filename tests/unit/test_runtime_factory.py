from unittest.mock import MagicMock

from src.runtimes.langchain_runtime import LangChainRuntime
from src.runtimes.runtime_factory import RuntimeFactory


def create_mock_config():
    config = MagicMock()

    values = {
        "llm.provider": "ollama",
        "llm.model": "llama3",
        "llm.base_url": "http://localhost:11434",
    }

    config.get.side_effect = lambda key, default=None: values.get(key, default)

    return config


def test_create_langchain_runtime():
    mock_config = create_mock_config()
    runtime = RuntimeFactory.create(
        runtime_type="langchain",
        config_manager=mock_config,
        tools=[],
    )

    assert isinstance(runtime, LangChainRuntime)
