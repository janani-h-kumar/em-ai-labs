from unittest.mock import MagicMock, patch

import pytest

from src.providers.ollama_provider import OllamaClient
from src.providers.provider_factory import ProviderFactory


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


@patch("src.providers.provider_factory.OllamaClient")
def test_create_ollama_provider(mock_ollama_client, mock_config):
    mock_instance = MagicMock(spec=OllamaClient)
    mock_ollama_client.return_value = mock_instance

    provider = ProviderFactory.get_provider(mock_config)

    mock_ollama_client.assert_called_once()
    assert provider == mock_instance
