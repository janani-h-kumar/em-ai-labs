from unittest.mock import MagicMock, patch

import pytest

from src.core.container import ServiceContainer
from src.memory.conversation_memory import InProcessMemory


@pytest.fixture
def mock_config():
    config = MagicMock()

    config_values = {
        "llm.provider": "ollama",
        "memory.backend": None,
        "persistence.type": "memory",
    }

    config.get.side_effect = lambda key, default=None: config_values.get(key, default)
    return config


def test_service_container_selects_default_memory_backend(mock_config):
    with patch("src.core.container.ProviderFactory.get_provider") as mock_provider_factory, patch(
        "src.core.container.ToolRegistry"
    ) as mock_tool_registry_class:
        mock_provider_factory.return_value = MagicMock()
        mock_tool_registry = MagicMock()
        mock_tool_registry_class.return_value = mock_tool_registry

        container = ServiceContainer(mock_config)

        assert isinstance(container.memory, InProcessMemory)
        assert container.memory_registry.has_backend("memory")
        assert container.memory_factory is not None


def test_service_container_uses_explicit_memory_backend_override(mock_config):
    mock_config.get.side_effect = lambda key, default=None: {
        "llm.provider": "ollama",
        "memory.backend": "memory",
        "persistence.type": "sqlite",
    }.get(key, default)

    with patch("src.core.container.ProviderFactory.get_provider") as mock_provider_factory, patch(
        "src.core.container.ToolRegistry"
    ) as mock_tool_registry_class:
        mock_provider_factory.return_value = MagicMock()
        mock_tool_registry = MagicMock()
        mock_tool_registry_class.return_value = mock_tool_registry

        container = ServiceContainer(mock_config)

        assert isinstance(container.memory, InProcessMemory)
        assert container.memory_registry.has_backend("memory")


def test_service_container_raises_for_unknown_memory_backend(mock_config):
    mock_config.get.side_effect = lambda key, default=None: {
        "llm.provider": "ollama",
        "memory.backend": "unknown",
        "persistence.type": "memory",
    }.get(key, default)

    with patch("src.core.container.ProviderFactory.get_provider") as mock_provider_factory, patch(
        "src.core.container.ToolRegistry"
    ) as mock_tool_registry_class:
        mock_provider_factory.return_value = MagicMock()
        mock_tool_registry = MagicMock()
        mock_tool_registry_class.return_value = mock_tool_registry

        with pytest.raises(ValueError, match="Unknown memory backend"):
            ServiceContainer(mock_config)
