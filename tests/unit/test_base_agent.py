from unittest.mock import MagicMock

import pytest

from src.agents.base_agent import (
    AgentExecutionError,
    AgentInitError,
    BaseAgent,
)


class DummyAgent(BaseAgent):
    def initialize(self) -> None:
        self.test_value = "initialized"

    def handle(self, message: str) -> str:
        return f"handled: {message}"


class FailingInitAgent(BaseAgent):
    def initialize(self) -> None:
        raise Exception("Initialization failed")

    def handle(self, message: str) -> str:
        return message


class TypedFailingInitAgent(BaseAgent):
    def initialize(self) -> None:
        raise AgentInitError("Typed init failure")

    def handle(self, message: str) -> str:
        return message


class FailingHandleAgent(BaseAgent):
    def initialize(self) -> None:
        pass

    def handle(self, message: str) -> str:
        raise AgentExecutionError("Handle failed")


@pytest.fixture
def mock_config():
    config = MagicMock()

    values = {
        "env.OPENWEATHER_API_KEY": "fake-key",
        "llm.provider": "ollama",
    }

    config.get.side_effect = lambda key, default=None: values.get(key, default)

    return config


def test_agent_initializes(mock_config):
    agent = DummyAgent(mock_config)

    assert agent.is_initialized() is True
    assert agent.test_value == "initialized"


def test_agent_has_config(mock_config):
    agent = DummyAgent(mock_config)

    assert agent.config_manager == mock_config


def test_get_config_returns_value(mock_config):
    agent = DummyAgent(mock_config)

    value = agent.get_config("env.OPENWEATHER_API_KEY")

    assert value == "fake-key"


def test_get_config_returns_default(mock_config):
    agent = DummyAgent(mock_config)

    value = agent.get_config("missing.key", "default")

    assert value == "default"


def test_handle_returns_response(mock_config):
    agent = DummyAgent(mock_config)

    response = agent.handle("hello")

    assert response == "handled: hello"


def test_health_check_initialized(mock_config):
    agent = DummyAgent(mock_config)

    health = agent.health_check()

    assert health["agent"] == "DummyAgent"
    assert health["status"] == "healthy"
    assert health["initialized"] is True
    assert "timestamp" in health


def test_agent_init_error_wrapped(mock_config):
    with pytest.raises(AgentInitError) as exc:
        FailingInitAgent(mock_config)

    assert "Failed to initialise FailingInitAgent" in str(exc.value)


def test_typed_agent_init_error_passthrough(mock_config):
    with pytest.raises(AgentInitError) as exc:
        TypedFailingInitAgent(mock_config)

    assert str(exc.value) == "Typed init failure"


def test_handle_execution_error(mock_config):
    agent = FailingHandleAgent(mock_config)

    with pytest.raises(AgentExecutionError):
        agent.handle("test")
