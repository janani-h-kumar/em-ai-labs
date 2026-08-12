from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.agents.agent_factory import AgentDependencyError, AgentFactory


def test_required_tool_dependency_is_injected():
    config = Mock()
    provider = Mock()
    tool = Mock(name="weather_tool")
    registry = Mock()
    registry.get_tool.return_value = tool
    registry._tool_instances = {"weather_tool": tool}

    factory = AgentFactory(SimpleNamespace(config_manager=config, provider=provider, tool_registry=registry))

    class Agent:
        def __init__(self, config_manager, base_llm_provider, weather_tool):
            self.weather_tool = weather_tool

    instance = factory.create(Agent)
    assert instance.weather_tool is tool


def test_missing_required_dependency_fails_before_constructor():
    config = Mock()
    provider = Mock()
    registry = Mock()
    registry.get_tool.return_value = None
    registry._tool_instances = {}

    factory = AgentFactory(SimpleNamespace(config_manager=config, provider=provider, tool_registry=registry))

    constructor_called = False

    class Agent:
        def __init__(self, config_manager, required_tool):
            nonlocal constructor_called
            constructor_called = True

    with pytest.raises(AgentDependencyError, match="required_tool"):
        factory.create(Agent)

    assert constructor_called is False
