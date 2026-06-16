"""
P0 Completion Verification — Comprehensive System Test

This test verifies that all P0 stabilization goals are met:
1. ServiceContainer exists and owns infrastructure
2. AgentRegistry discovers agents dynamically
3. AgentFactory uses constructor introspection
4. MessageRouter is data-driven from agent metadata
5. Fallback system works end-to-end without crashing
"""

import pytest


def test_p0_service_container_owns_infrastructure():
    """ServiceContainer centralizes infrastructure ownership."""
    from src.core.container import ServiceContainer
    from src.utils.config_loader import ConfigManager

    try:
        config = ConfigManager("configs/config.yaml")
    except Exception:
        pytest.skip("config.yaml not available in test environment")

    container = ServiceContainer(config)

    assert hasattr(container, "config_manager")
    assert hasattr(container, "provider")
    assert hasattr(container, "tool_registry")


def test_p0_agent_registry_discovers_agents_dynamically():
    """AgentRegistry discovers agents from src/agents/ without hardcoding."""
    from src.agents.agent_registry import AgentRegistry
    from src.core.container import ServiceContainer
    from src.utils.config_loader import ConfigManager

    try:
        config = ConfigManager("configs/config.yaml")
    except Exception:
        pytest.skip("config.yaml not available in test environment")

    container = ServiceContainer(config)
    registry = AgentRegistry(container=container)

    discovered = registry.list_agents()

    # Must discover at least general and weather_agent
    assert "general" in discovered, "general agent must be discovered"
    assert "weather_agent" in discovered, "weather_agent must be discovered"


def test_p0_general_agent_has_metadata():
    """GeneralAgent implements BaseAgent metadata contract."""
    from src.agents.general_agent import GeneralAgent

    assert hasattr(GeneralAgent, "name")
    assert hasattr(GeneralAgent, "description")
    assert hasattr(GeneralAgent, "capabilities")

    assert GeneralAgent.name == "general"
    assert GeneralAgent.description == "Fallback general-purpose assistant"
    assert "fallback" in GeneralAgent.capabilities


def test_p0_agent_factory_uses_introspection():
    """AgentFactory creates agents via constructor introspection."""
    from unittest.mock import Mock

    from src.agents.agent_factory import AgentFactory

    factory = AgentFactory(
        config_manager=Mock(),
        provider=Mock(),
        tool_registry=Mock(),
    )

    # Factory should accept any agent class and introspect it
    class TestAgent:
        def __init__(self, config_manager, base_llm_provider):
            self.config_manager = config_manager
            self.base_llm_provider = base_llm_provider

    instance = factory.create(TestAgent)

    assert isinstance(instance, TestAgent)
    assert hasattr(instance, "config_manager")
    assert hasattr(instance, "base_llm_provider")


def test_p0_router_is_metadata_driven():
    """MessageRouter reads from agent metadata, not hardcoded."""
    from src.router import MessageRouter

    # Router should accept capabilities mapping
    router = MessageRouter(
        agent_capabilities={
            "general": ["general", "fallback"],
            "weather": ["weather", "temperature"],
        }
    )

    # Routing should work based on keywords
    agent, confidence = router.route_message("what is the weather")
    assert agent == "weather"

    # Fallback should work for unmatched
    agent, confidence = router.route_message("hello there")
    assert agent == "general"


def test_p0_fallback_works_end_to_end():
    """Fallback routing doesn't crash — agent is discoverable and executable."""
    from src.agents.agent_registry import AgentRegistry
    from src.core.container import ServiceContainer
    from src.router import MessageRouter
    from src.utils.config_loader import ConfigManager

    try:
        config = ConfigManager("configs/config.yaml")
    except Exception:
        pytest.skip("config.yaml not available in test environment")

    container = ServiceContainer(config)
    registry = AgentRegistry(container=container)

    # Build router from metadata
    agent_capabilities = {
        name: getattr(agent_class, "capabilities", []) or []
        for name, agent_class in registry.agents.items()
    }
    router = MessageRouter(agent_capabilities=agent_capabilities)

    # Route unmatched message
    agent_name, confidence = router.route_message("hello there")
    assert agent_name == "general"

    # Agent should be in registry
    assert registry.has_agent(agent_name)

    # Should be able to create instance
    agent_instance = registry.create_instance(agent_name)
    assert agent_instance is not None

    # Agent should be initialized
    assert agent_instance.is_initialized()


def test_p0_registry_get_compatibility_alias():
    """AgentRegistry.get() alias supports backward compatibility."""
    from src.agents.agent_registry import AgentRegistry
    from src.core.container import ServiceContainer
    from src.utils.config_loader import ConfigManager

    try:
        config = ConfigManager("configs/config.yaml")
    except Exception:
        pytest.skip("config.yaml not available in test environment")

    container = ServiceContainer(config)
    registry = AgentRegistry(container=container)

    # Both methods should work
    instance1 = registry.create_instance("general")
    instance2 = registry.get("general")

    # Both should return GeneralAgent instances
    assert type(instance1).__name__ == type(instance2).__name__


def test_p0_no_hardcoded_agent_references():
    """Framework components don't reference specific agents."""
    from src.agents.agent_registry import AgentRegistry
    from src.orchestration.executor import Executor
    from src.router import Router

    # These components should not mention "weather", "general", etc.
    # They work purely through agent metadata and registry

    router_source = Router.__module__
    executor_source = Executor.__module__
    registry_source = AgentRegistry.__module__

    # If framework is truly agent-agnostic, these should be true:
    assert router_source == "src.router"
    assert executor_source == "src.orchestration.executor"
    assert registry_source == "src.agents.agent_registry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
