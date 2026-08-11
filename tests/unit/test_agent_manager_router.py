"""Tests for ApplicationService router initialization from agent metadata."""

from unittest.mock import Mock, patch

from src.agents.agent_descriptor import AgentDescriptor


def _mock_container() -> Mock:
    container = Mock()
    container.config_manager = Mock()
    container.provider = Mock()
    container.memory = Mock()
    container.tool_registry = Mock()
    container.tool_registry.get_langchain_tools.return_value = []
    return container


def _descriptors() -> list[AgentDescriptor]:
    class MockGeneralAgent:
        name = "general"
        capabilities = ["general", "fallback"]

    class MockWeatherAgent:
        name = "weather_agent"
        capabilities = ["weather", "temperature", "forecast"]

    return [
        AgentDescriptor(
            name="general",
            description="Fallback general-purpose assistant",
            capabilities=MockGeneralAgent.capabilities,
            agent_class=MockGeneralAgent,
        ),
        AgentDescriptor(
            name="weather_agent",
            description="Weather assistant",
            capabilities=MockWeatherAgent.capabilities,
            agent_class=MockWeatherAgent,
        ),
    ]


def test_application_service_builds_router_from_agent_metadata():
    """ApplicationService builds MessageRouter from AgentDescriptor metadata."""
    with patch("src.application_service.ServiceContainer") as mock_container_class:
        mock_container_class.return_value = _mock_container()

        with patch("src.application_service.ConfigManager"):
            with patch("src.application_service.AgentRegistry") as mock_registry_class:
                mock_registry = Mock()
                mock_registry.descriptors.return_value = _descriptors()
                mock_registry_class.return_value = mock_registry

                with patch("src.application_service.Orchestrator"):
                    from src.application_service import ApplicationService

                    manager = ApplicationService()

                    assert manager.router is not None
                    assert "general" in manager.router.agent_patterns
                    assert "weather_agent" in manager.router.agent_patterns
                    assert manager.router.agent_patterns["general"]
                    assert manager.router.agent_patterns["weather_agent"]


def test_application_service_router_handles_fallback_correctly():
    """MessageRouter returns the general fallback when nothing matches."""
    with patch("src.application_service.ServiceContainer") as mock_container_class:
        mock_container_class.return_value = _mock_container()

        with patch("src.application_service.ConfigManager"):
            with patch("src.application_service.AgentRegistry") as mock_registry_class:
                mock_registry = Mock()
                mock_registry.descriptors.return_value = _descriptors()
                mock_registry_class.return_value = mock_registry

                with patch("src.application_service.Orchestrator"):
                    from src.application_service import ApplicationService

                    manager = ApplicationService()
                    result = manager.router.route_message("hello there")

                    assert result.agent_name == "general"
                    assert result.confidence == 0.0
