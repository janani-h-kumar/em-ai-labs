"""
Architecture contract tests.

These tests protect the core harness design and prevent
future regressions as new agents are added.
"""

import inspect
import pkgutil

import src.agents as agents_package
from src.agents.base_agent import BaseAgent
from src.core.container import ServiceContainer


def _discover_agent_classes():
    """
    Discover all BaseAgent subclasses.
    """

    import importlib

    agent_classes = []

    for _, module_name, _ in pkgutil.iter_modules(agents_package.__path__):
        if module_name == "base_agent":
            continue

        module = importlib.import_module(f"src.agents.{module_name}")

        for _, obj in inspect.getmembers(
            module,
            inspect.isclass,
        ):
            if issubclass(obj, BaseAgent) and obj is not BaseAgent:
                agent_classes.append(obj)

    return agent_classes


# ------------------------------------------------------------------
# Container Contracts
# ------------------------------------------------------------------


def test_service_container_owns_core_dependencies():
    """
    ServiceContainer must remain the owner
    of infrastructure dependencies.
    """

    required_attributes = [
        "config_manager",
        "provider",
        "tool_registry",
        "memory",
    ]

    container_members = vars(ServiceContainer)

    for attribute in required_attributes:
        assert attribute in ServiceContainer.__dict__ or hasattr(ServiceContainer, attribute), (
            f"Missing container dependency: {attribute}"
        )


# ------------------------------------------------------------------
# Agent Contracts
# ------------------------------------------------------------------


def test_all_agents_inherit_base_agent():
    """
    Every agent must inherit BaseAgent.
    """

    agent_classes = _discover_agent_classes()

    assert agent_classes, "No agents discovered"

    for agent_class in agent_classes:
        assert issubclass(
            agent_class,
            BaseAgent,
        )


def test_all_agents_implement_async_handle():
    """
    Every agent must expose async handle().
    """

    agent_classes = _discover_agent_classes()

    for agent_class in agent_classes:
        assert hasattr(
            agent_class,
            "handle",
        ), f"{agent_class.__name__} missing handle()"

        assert inspect.iscoroutinefunction(agent_class.handle), (
            f"{agent_class.__name__}.handle must be async"
        )


# ------------------------------------------------------------------
# Statelessness Contracts
# ------------------------------------------------------------------


FORBIDDEN_STATE_FIELDS = {
    "history",
    "conversation_history",
    "messages",
    "current_user",
    "session",
    "session_id",
    "user_id",
    "last_response",
    "last_result",
    "request",
    "request_id",
}


def test_agents_do_not_declare_request_state():
    """
    Agents must behave as stateless services.

    Request state belongs in ExecutionContext.
    Conversation state belongs in Memory.
    """

    agent_classes = _discover_agent_classes()

    for agent_class in agent_classes:
        class_attributes = vars(agent_class)

        overlap = set(class_attributes.keys()) & FORBIDDEN_STATE_FIELDS

        assert not overlap, f"{agent_class.__name__} declares forbidden state fields: {overlap}"


# ------------------------------------------------------------------
# Dependency Injection Contracts
# ------------------------------------------------------------------


def test_agents_do_not_construct_config_manager():
    """
    Agents must receive ConfigManager via DI.
    """

    agent_classes = _discover_agent_classes()

    for agent_class in agent_classes:
        source = inspect.getsource(agent_class)

        assert "ConfigManager(" not in source, (
            f"{agent_class.__name__} creates ConfigManager directly"
        )


def test_agents_do_not_construct_tool_registry():
    """
    Agents must receive tools via DI.
    """

    agent_classes = _discover_agent_classes()

    for agent_class in agent_classes:
        source = inspect.getsource(agent_class)

        assert "ToolRegistry(" not in source, (
            f"{agent_class.__name__} creates ToolRegistry directly"
        )


def test_agents_do_not_construct_provider_factory():
    """
    Agents must receive providers via DI.
    """

    agent_classes = _discover_agent_classes()

    for agent_class in agent_classes:
        source = inspect.getsource(agent_class)

        assert "ProviderFactory" not in source, f"{agent_class.__name__} creates providers directly"
