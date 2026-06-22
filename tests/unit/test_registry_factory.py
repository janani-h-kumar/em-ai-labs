from types import SimpleNamespace
from unittest.mock import Mock

from src.agents.agent_factory import AgentFactory
from src.agents.agent_registry import AgentRegistry


def test_agentfactory_dynamic_injection():
    """
    Verify AgentFactory injects dependencies
    from the container using constructor introspection.
    """

    config_manager = Mock()
    provider = Mock()

    class DummyTool:
        pass

    tool = DummyTool()

    tool_registry = Mock()
    tool_registry.get_tool.return_value = tool

    container = SimpleNamespace(
        config_manager=config_manager,
        provider=provider,
        tool_registry=tool_registry,
    )

    factory = AgentFactory(container)

    class DummyAgent:
        def __init__(
            self,
            config_manager,
            base_llm_provider,
            my_tool,
        ):
            self.config_manager = config_manager
            self.base_llm_provider = base_llm_provider
            self.my_tool = my_tool

    instance = factory.create(DummyAgent)

    assert isinstance(instance, DummyAgent)

    assert instance.config_manager is config_manager
    assert instance.base_llm_provider is provider
    assert instance.my_tool is tool


def test_registry_create_instance():
    """
    Verify registry creates agent instances
    through AgentFactory.
    """

    container = SimpleNamespace(
        config_manager=Mock(),
        provider=Mock(),
        tool_registry=Mock(),
    )

    registry = AgentRegistry(container)

    class SimpleAgent:
        name = "simple_agent"

        def __init__(self, config_manager):
            self.config_manager = config_manager

    registry.agents["simple_agent"] = SimpleAgent

    instance = registry.create_instance("simple_agent")

    assert isinstance(instance, SimpleAgent)
    assert instance.config_manager is container.config_manager


def test_registry_get_is_alias_for_create_instance():
    """
    Verify registry.get() returns an agent instance.
    """

    container = SimpleNamespace(
        config_manager=Mock(),
        provider=Mock(),
        tool_registry=Mock(),
    )

    registry = AgentRegistry(container)

    class SimpleAgent:
        name = "simple_agent"

        def __init__(self, config_manager):
            self.config_manager = config_manager

    registry.agents["simple_agent"] = SimpleAgent

    instance = registry.get("simple_agent")

    assert isinstance(instance, SimpleAgent)
    assert instance.config_manager is container.config_manager
