from unittest.mock import MagicMock

import pytest

from src.providers.ollama_provider import OllamaClient
from src.providers.provider_factory import ProviderFactory


@pytest.fixture
def mock_config():
    config = MagicMock()

    def _get(key, default=None):
        if key == "llm.provider":
            return config.provider
        return default

    config.get = _get
    config.provider = "ollama"
    return config


def test_create_ollama_provider(mock_config):
    mock_config.get.return_value = "ollama"

    provider = ProviderFactory.get_provider(mock_config)

    assert isinstance(provider, OllamaClient)
