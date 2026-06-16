from unittest.mock import Mock


def test_agentfactory_dynamic_injection():
    from src.agents.agent_factory import AgentFactory

    # Mocks for dependencies
    config_manager = Mock()
    provider = Mock()

    class DummyTool:
        pass

    tool_instance = DummyTool()

    tool_registry = Mock()
    tool_registry.get_tool.return_value = tool_instance

    factory = AgentFactory(
        config_manager=config_manager, provider=provider, tool_registry=tool_registry
    )

    # Define a dummy agent class expecting specific parameters
    class DummyAgent:
        def __init__(self, config_manager, base_llm_provider, my_tool):
            self.config_manager = config_manager
            self.base_llm_provider = base_llm_provider
            self.my_tool = my_tool

    instance = factory.create(DummyAgent)

    assert isinstance(instance, DummyAgent)
    assert instance.config_manager is config_manager
    assert instance.base_llm_provider is provider
    # Tool injection resolves by parameter name via tool_registry.get_tool
    assert instance.my_tool is tool_instance


def test_registry_create_instance():
    from types import SimpleNamespace

    from src.agents.agent_registry import AgentRegistry

    # Prepare a minimal container for the registry
    config_manager = Mock()
    provider = Mock()

    class SomeTool:
        pass

    tool_registry = Mock()
    tool_registry.get_tool.return_value = SomeTool()

    container = SimpleNamespace(
        config_manager=config_manager, provider=provider, tool_registry=tool_registry
    )

    registry = AgentRegistry(container=container)

    # Add a simple agent class into the registry mapping
    class SimpleAgent:
        name = "simple_agent"

        def __init__(self, config_manager):
            self.config_manager = config_manager

    registry.agents["simple_agent"] = SimpleAgent

    instance = registry.create_instance("simple_agent")

    assert isinstance(instance, SimpleAgent)
    assert instance.config_manager is config_manager


def test_registry_get_alias_returns_instance():
    from types import SimpleNamespace

    from src.agents.agent_registry import AgentRegistry

    config_manager = Mock()
    provider = Mock()

    class SomeTool:
        pass

    tool_registry = Mock()
    tool_registry.get_tool.return_value = SomeTool()

    container = SimpleNamespace(
        config_manager=config_manager, provider=provider, tool_registry=tool_registry
    )

    registry = AgentRegistry(container=container)

    class SimpleAgent:
        name = "simple_agent"

        def __init__(self, config_manager):
            self.config_manager = config_manager

    registry.agents["simple_agent"] = SimpleAgent

    instance = registry.get("simple_agent")

    assert isinstance(instance, SimpleAgent)
    assert instance.config_manager is config_manager
