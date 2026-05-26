from unittest.mock import MagicMock

import pytest

from src.memory.conversation_memory import (
    InProcessMemory,
)
from src.runtimes.langchain_runtime import (
    LangChainRuntime,
)


@pytest.fixture
def mock_config():
    config = MagicMock()

    config_values = {
        "llm.provider": "ollama",
        "llm.model": "llama3",
        "llm.base_url": "http://localhost:11434",
    }

    config.get.side_effect = lambda key, default=None: config_values.get(key, default)

    return config


def test_runtime_uses_injected_memory(mock_config):

    memory = InProcessMemory()

    runtime = LangChainRuntime(memory=memory, config_manager=mock_config)

    history = runtime._get_session_history("abc")

    assert history is memory.get_history("abc")
