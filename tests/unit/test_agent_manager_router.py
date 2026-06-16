"""
Test AgentManager router initialization from agent metadata.
"""

from unittest.mock import Mock, patch


def test_agent_manager_builds_router_from_agent_metadata():
    """Verify AgentManager builds router from agent registry capabilities."""

    with patch("src.agent_manager.ServiceContainer") as mock_container_class:
        # Mock container to avoid initializing real providers/tools
        mock_container = Mock()
        mock_container.config_manager = Mock()
        mock_container.provider = Mock()
        mock_container.tool_registry = Mock()
        mock_container.tool_registry.get_langchain_tools.return_value = []

        mock_container_class.return_value = mock_container

        with patch("src.agent_manager.ConfigManager"):
            with patch("src.agent_manager.AgentRegistry") as mock_registry_class:
                # Mock AgentRegistry to return test agents
                mock_registry = Mock()

                # Simulate discovered agents with capabilities
                class MockGeneralAgent:
                    name = "general"
                    capabilities = ["general", "fallback"]

                class MockWeatherAgent:
                    name = "weather_agent"
                    capabilities = ["weather", "temperature", "forecast"]

                mock_registry.agents = {
                    "general": MockGeneralAgent,
                    "weather_agent": MockWeatherAgent,
                }

                mock_registry_class.return_value = mock_registry

                with patch("src.agent_manager.Orchestrator"):
                    from src.agent_manager import AgentManager

                    # Initialize AgentManager (this will build router)
                    manager = AgentManager()

                    # Verify router was created with agent capabilities
                    assert manager.router is not None
                    assert hasattr(manager.router, "agent_patterns")

                    # Verify router has patterns for both agents
                    assert "general" in manager.router.agent_patterns
                    assert "weather_agent" in manager.router.agent_patterns


def test_agent_manager_router_handles_fallback_correctly():
    """Verify router returns 'general' fallback when no specific agent matches."""

    with patch("src.agent_manager.ServiceContainer") as mock_container_class:
        mock_container = Mock()
        mock_container.config_manager = Mock()
        mock_container.provider = Mock()
        mock_container.tool_registry = Mock()
        mock_container.tool_registry.get_langchain_tools.return_value = []

        mock_container_class.return_value = mock_container

        with patch("src.agent_manager.ConfigManager"):
            with patch("src.agent_manager.AgentRegistry") as mock_registry_class:
                mock_registry = Mock()

                class MockGeneralAgent:
                    name = "general"
                    capabilities = ["general", "fallback"]

                class MockWeatherAgent:
                    name = "weather_agent"
                    capabilities = ["weather"]

                mock_registry.agents = {
                    "general": MockGeneralAgent,
                    "weather_agent": MockWeatherAgent,
                }

                mock_registry_class.return_value = mock_registry

                with patch("src.agent_manager.Orchestrator"):
                    from src.agent_manager import AgentManager

                    manager = AgentManager()

                    # Route a message that doesn't match specific agents
                    agent, confidence = manager.router.route_message("hello there")

                    # Should fall back to 'general'
                    assert agent == "general"
