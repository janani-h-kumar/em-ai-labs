from unittest.mock import Mock

import pytest

from src.providers.provider_factory import ProviderFactory


def test_factory_exists():
    factory = ProviderFactory()
    assert factory is not None


def test_create_ollama_provider():
    config = Mock()
    config.get.return_value = "ollama"

    provider = ProviderFactory.create_provider(config)

    assert provider is not None


def test_create_claude_provider():
    config = Mock()
    config.get.return_value = "claude"

    provider = ProviderFactory.create_provider(config)

    assert provider is not None


def test_unknown_provider_raises():
    config = Mock()
    config.get.return_value = "invalid"

    with pytest.raises(ValueError):
        ProviderFactory.create_provider(config)
