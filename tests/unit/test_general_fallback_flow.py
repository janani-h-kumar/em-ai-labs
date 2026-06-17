"""
End-to-end verification: Router → Registry → Executor flow for general fallback.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_executor_routes_and_creates_general_agent():
    """
    Verify the executor can successfully route to 'general' and instantiate it.

    Flow:
    1. Router receives unmatched message → returns 'general'
    2. Executor receives 'general' agent name → calls registry.create_instance()
    3. Registry creates GeneralAgent instance → success
    """

    with patch("src.orchestration.executor.logging"):
        from src.orchestration.executor import Executor
        from src.router import MessageRouter

        # Create a mock registry that simulates discovered agents
        mock_registry = Mock()

        # Create a simple mock agent instance
        mock_agent_instance = AsyncMock()
        mock_agent_instance.handle = AsyncMock(return_value="General response")

        # registry.create_instance('general') should return the mock agent
        mock_registry.create_instance.return_value = mock_agent_instance

        # Create router and executor
        router = MessageRouter(
            agent_capabilities={
                "weather_agent": ["weather", "temperature"],
            }
        )

        executor = Executor(
            agent_registry=mock_registry,
            router=router,
        )

        # Create a test task for routing
        from src.orchestration.models import ExecutionContext, Task, TaskStatus

        task = Task(
            id="test-task-1",
            description="hello there",  # No weather keywords → fallback
        )

        context = ExecutionContext(session_id="session-1", goal="hello there")

        # Execute the task (this will route and create the agent)
        result = await executor.execute_task(task, context)
        assert isinstance(result, str)

        # Verify the agent was created with 'general' name
        mock_registry.create_instance.assert_called_once_with("general")

        # Verify the agent was called
        mock_agent_instance.handle.assert_called_once()

        # Verify the result was stored
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "General response"
        assert context.completed_tasks[task.id] == "General response"


@pytest.mark.asyncio
async def test_full_flow_general_agent_discovery_to_execution():
    """
    Simulate the full bootstrap flow without real external dependencies.

    Verifies:
    - AgentRegistry discovers general agent
    - Router is initialized from agent capabilities
    - Executor routes and executes successfully
    """

    with patch("src.core.container.ProviderFactory") as mock_provider_factory:
        with patch("src.core.container.ToolRegistry") as mock_tool_registry_class:
            with patch("src.providers.provider_factory.OllamaClient"):
                with patch("src.providers.provider_factory.ClaudeProvider"):
                    # Mock provider
                    mock_provider = Mock()
                    mock_provider.chat_completion = Mock(return_value="Test response")
                    mock_provider_factory.get_provider.return_value = mock_provider

                    # Mock tool registry
                    mock_tool_registry = Mock()
                    mock_tool_registry.get_tool.return_value = None
                    mock_tool_registry_class.return_value = mock_tool_registry

                    # Create real ConfigManager (uses real YAML)
                    from src.utils.config_loader import ConfigManager

                    try:
                        config = ConfigManager("configs/config.yaml")
                    except Exception:
                        # If config missing in test env, use minimal mock
                        config = Mock()
                        config.get = Mock(return_value="ollama")

                    # Create real container
                    from src.core.container import ServiceContainer

                    container = ServiceContainer(config)

                    # Create real registry (this will discover agents)
                    from src.agents.agent_registry import AgentRegistry

                    registry = AgentRegistry(container=container)

                    # Verify discovery
                    assert registry.has_agent("general"), "general agent should be discovered"

                    # Create router from agent metadata
                    from src.router import MessageRouter

                    agent_capabilities = {
                        name: getattr(agent_class, "capabilities", []) or []
                        for name, agent_class in registry.agents.items()
                    }

                    router = MessageRouter(agent_capabilities=agent_capabilities)

                    # Verify routing
                    agent_name, confidence = router.route_message("hello there")
                    assert agent_name == "general", "Unmatched message should route to general"

                    # Verify executor can handle the route
                    from src.orchestration.executor import Executor
                    from src.orchestration.models import ExecutionContext, Task

                    executor = Executor(
                        agent_registry=registry,
                        router=router,
                    )

                    task = Task(
                        id="test-1",
                        description="hello there",
                    )

                    context = ExecutionContext(session_id="test-session", goal="hello there")

                    # This should NOT raise "Agent 'general' not found"
                    try:
                        result = await executor.execute_task(task, context)
                        # Success — agent was created and executed
                        assert result is not None
                    except ValueError as e:
                        if "not found" in str(e):
                            pytest.fail(f"Agent discovery/routing failed: {e}")
                        raise
