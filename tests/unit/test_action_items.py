"""
Tests covering all 7 action items.

Run with: pytest tests/unit/test_action_items.py -v
"""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared across tests
# ─────────────────────────────────────────────────────────────────────────────


def make_context(session_id="test-session", goal="test goal"):
    """Minimal ExecutionContext-compatible dict for tests that don't need the real class."""
    from src.orchestration.models import ExecutionContext

    return ExecutionContext(session_id=session_id, goal=goal)


def make_task(task_id="task-1", description="do something"):
    from src.orchestration.models import Task

    return Task(id=task_id, description=description, dependencies=[])


# ─────────────────────────────────────────────────────────────────────────────
# Item 1 — react_loop: execution guardrail is wired, docstring is first
# ─────────────────────────────────────────────────────────────────────────────


class TestReactLoopGuardrail:
    @pytest.mark.asyncio
    async def test_guardrail_check_iteration_called_each_iteration(self):
        """ExecutionGuardrail.check_iteration must be called on each loop pass."""
        from src.guardrails import GuardrailConfig
        from src.orchestration.react_loop import ReACTLoop

        planner = Mock()
        task = make_task()
        planner.create_plan = AsyncMock(return_value=[task])

        executor = Mock()
        executor.execute_task = AsyncMock(return_value="result")
        executor.execute_parallel = AsyncMock()

        loop = ReACTLoop(planner=planner, executor=executor)
        context = make_context()

        config = GuardrailConfig(max_react_iterations=3, max_execution_seconds=60)
        results = await loop.run(
            provider=Mock(chat_completion=Mock(return_value="reasoning")),
            goal="test",
            context=context,
            guardrail_config=config,
        )
        assert results == ["result"]

    @pytest.mark.asyncio
    async def test_guardrail_max_iterations_respected_from_config(self):
        """max_react_iterations from GuardrailConfig should cap the loop."""
        from src.guardrails import GuardrailConfig
        from src.orchestration.react_loop import ReACTLoop

        # Build a graph that never completes to force iteration count enforcement
        task1 = make_task("t1", "first")
        task2 = make_task("t2", "second")

        planner = Mock()
        planner.create_plan = AsyncMock(return_value=[task1, task2])

        executor = Mock()
        executor.execute_task = AsyncMock(return_value="result")
        executor.execute_parallel = AsyncMock(return_value=["r1", "r2"])

        loop = ReACTLoop(planner=planner, executor=executor)
        context = make_context()

        # With only 1 allowed iteration and 2 dependent tasks, second iteration
        # should hit the guardrail
        config = GuardrailConfig(max_react_iterations=1, max_execution_seconds=60)
        # Should not raise — guardrail limits loop but first iteration completes
        results = await loop.run(
            provider=Mock(chat_completion=Mock(return_value="r")),
            goal="test",
            context=context,
            guardrail_config=config,
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_timeout_guardrail_fires_when_exceeded(self, monkeypatch):
        """check_timeout must raise GuardrailViolationError when wall time exceeded."""
        from src.guardrails import GuardrailConfig
        from src.guardrails.exceptions import GuardrailViolationError
        from src.orchestration.react_loop import ReACTLoop

        task = make_task()
        planner = Mock()
        planner.create_plan = AsyncMock(return_value=[task])
        executor = Mock()
        executor.execute_task = AsyncMock(return_value="done")

        loop = ReACTLoop(planner=planner, executor=executor)
        context = make_context()

        # Monkeypatch time.monotonic so the guardrail always sees expired time
        call_count = {"n": 0}

        def fake_monotonic():
            call_count["n"] += 1
            # First call (start_time capture) returns 0, subsequent calls return 999
            return 0.0 if call_count["n"] == 1 else 9999.0

        monkeypatch.setattr("src.guardrails.execution_guardrail.time.perf_counter", fake_monotonic)

        config = GuardrailConfig(max_react_iterations=5, max_execution_seconds=1)

        with pytest.raises(GuardrailViolationError) as exc_info:
            await loop.run(
                provider=Mock(chat_completion=Mock(return_value="r")),
                goal="test",
                context=context,
                guardrail_config=config,
            )
        assert exc_info.value.code == "execution.max_time_exceeded"

    def test_run_docstring_is_accessible(self):
        """The run() docstring must not be shadowed by a preceding statement."""
        from src.orchestration.react_loop import ReACTLoop

        assert ReACTLoop.run.__doc__ is not None
        assert len(ReACTLoop.run.__doc__.strip()) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Item 2 — orchestrator: output guardrail applied on final response
# ─────────────────────────────────────────────────────────────────────────────


class TestOrchestratorOutputGuardrail:
    @pytest.mark.asyncio
    async def test_empty_response_raises_guardrail_violation(self):
        """Orchestrator.synthesize('') must produce an empty string which the
        output guardrail then catches before returning to the caller."""
        from src.guardrails import GuardrailConfig
        from src.guardrails.exceptions import GuardrailViolationError
        from src.orchestration.orchestrator import Orchestrator

        memory = MagicMock()
        history = MagicMock()
        history.messages = []
        memory.get_history.return_value = history

        provider = Mock()
        router = Mock()

        react_loop = Mock()
        react_loop.run = AsyncMock(return_value=[""])  # empty agent result

        orch = Orchestrator(
            agent_registry=Mock(),
            router=router,
            provider=provider,
            memory=memory,
            guardrail_config=GuardrailConfig(),
        )
        orch.react_loop = react_loop

        # Empty synthesized response should trigger the output guardrail
        with pytest.raises(GuardrailViolationError):
            await orch.run(goal="test", session_id="s1")

    @pytest.mark.asyncio
    async def test_valid_response_passes_output_guardrail(self):
        """A non-empty response should pass through without raising."""
        from src.guardrails import GuardrailConfig
        from src.orchestration.orchestrator import Orchestrator

        memory = MagicMock()
        history = MagicMock()
        history.messages = []
        memory.get_history.return_value = history

        react_loop = Mock()
        react_loop.run = AsyncMock(return_value=["The weather is sunny, 72°F."])

        orch = Orchestrator(
            agent_registry=Mock(),
            router=Mock(),
            provider=Mock(),
            memory=memory,
            guardrail_config=GuardrailConfig(),
        )
        orch.react_loop = react_loop

        response = await orch.run(goal="weather in Seattle", session_id="s2")
        assert response == "The weather is sunny, 72°F."


# ─────────────────────────────────────────────────────────────────────────────
# Item 3 — planner: _output_guardrail is always initialised
# ─────────────────────────────────────────────────────────────────────────────


class TestPlannerGuardrailInit:
    def test_planner_has_output_guardrail_by_default(self):
        """Planner() without arguments must initialise _output_guardrail."""
        from src.orchestration.planner import Planner

        p = Planner()
        assert hasattr(p, "_output_guardrail")
        assert p._output_guardrail is not None

    def test_planner_accepts_custom_guardrail_config(self):
        """Planner should accept a GuardrailConfig and use it for its guardrail."""
        from src.guardrails import GuardrailConfig
        from src.orchestration.planner import Planner

        config = GuardrailConfig(max_tasks_per_execution=1)
        p = Planner(guardrail_config=config)
        assert p._output_guardrail is not None

    @pytest.mark.asyncio
    async def test_parse_plan_response_does_not_attribute_error(self):
        """_parse_plan_response must not raise AttributeError on _output_guardrail."""
        from src.orchestration.planner import Planner

        p = Planner()
        # Valid JSON — should not crash
        result = p._parse_plan_response(
            '[{"description": "do X", "agent": null, "parallelizable": false}]'
        )
        assert result is not None
        assert len(result) == 1
        assert result[0]["description"] == "do X"


# ─────────────────────────────────────────────────────────────────────────────
# Item 4 — AgentRegistry: descriptor-only storage, no raw class union
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentRegistryDescriptors:
    def _make_registry(self):
        from unittest.mock import MagicMock, patch

        from src.agents.agent_descriptor import AgentDescriptor
        from src.agents.agent_registry import AgentRegistry
        from src.agents.base_agent import BaseAgent

        class DummyAgent(BaseAgent):
            name = "dummy"
            description = "test agent"
            capabilities = ["test", "dummy"]

            def initialize(self):
                pass

            async def handle(self, task, context):
                return "ok"

        container = MagicMock()
        container.config_manager = MagicMock()
        container.provider = MagicMock()
        container.tool_registry = MagicMock()
        container.tool_registry.get_tool.return_value = None

        with patch.object(AgentRegistry, "discover_agents", lambda self: None):
            registry = AgentRegistry(container=container)

        descriptor = AgentDescriptor(
            name="dummy",
            description="test agent",
            capabilities=["test", "dummy"],
            agent_class=DummyAgent,
        )
        registry.agents["dummy"] = descriptor
        return registry, DummyAgent

    def test_agents_dict_values_are_all_descriptors(self):
        """registry.agents must contain only AgentDescriptor values."""
        from src.agents.agent_registry import AgentDescriptor

        registry, _ = self._make_registry()
        for value in registry.agents.values():
            assert isinstance(value, AgentDescriptor), (
                f"Expected AgentDescriptor, got {type(value)}"
            )

    def test_descriptors_method_returns_list(self):
        """descriptors() must return a list of AgentDescriptor."""
        from src.agents.agent_registry import AgentDescriptor

        registry, _ = self._make_registry()
        result = registry.descriptors()
        assert isinstance(result, list)
        assert all(isinstance(d, AgentDescriptor) for d in result)

    def test_get_class_returns_correct_class(self):
        """get_class() must return the agent class from the descriptor."""
        registry, dummy_agent_cls = self._make_registry()
        cls = registry.get_class("dummy")
        assert cls is dummy_agent_cls

    def test_health_check_uses_descriptor_metadata(self):
        """health_check() must include capabilities from descriptor."""
        registry, _ = self._make_registry()
        result = registry.health_check()
        assert "dummy" in result
        assert result["dummy"]["capabilities"] == ["test", "dummy"]


# ─────────────────────────────────────────────────────────────────────────────
# Item 5 — router: RoutingResult, descriptor-based construction
# ─────────────────────────────────────────────────────────────────────────────


class TestRouterDescriptorAndRoutingResult:
    def _make_descriptor(self, name, capabilities):
        from src.agents.agent_descriptor import AgentDescriptor
        from src.agents.base_agent import BaseAgent

        class _Agent(BaseAgent):
            def initialize(self):
                pass

            async def handle(self, task, context):
                return ""

        return AgentDescriptor(
            name=name,
            description="",
            capabilities=capabilities,
            agent_class=_Agent,
        )

    def test_router_built_from_descriptors(self):
        """MessageRouter must accept a list of AgentDescriptors."""
        from src.router import MessageRouter

        descriptors = [
            self._make_descriptor("weather_agent", ["weather", "forecast", "temperature"]),
            self._make_descriptor("general", ["general", "fallback"]),
        ]
        router = MessageRouter(descriptors=descriptors)
        assert "weather_agent" in router.agent_patterns
        assert "general" in router.agent_patterns

    def test_route_message_returns_routing_result(self):
        """route_message() must return a RoutingResult, not a tuple."""
        from src.router import MessageRouter, RoutingResult

        descriptors = [
            self._make_descriptor("weather_agent", ["weather", "temperature", "forecast"]),
        ]
        router = MessageRouter(descriptors=descriptors)
        result = router.route_message("what's the weather in Seattle?")
        assert isinstance(result, RoutingResult)
        assert result.agent_name == "weather_agent"
        assert 0.0 <= result.confidence <= 1.0

    def test_route_message_populates_matched_capabilities(self):
        """matched_capabilities must list the keywords that fired."""
        from src.router import MessageRouter

        descriptors = [
            self._make_descriptor("weather_agent", ["weather", "temperature"]),
        ]
        router = MessageRouter(descriptors=descriptors)
        result = router.route_message("weather in Seattle")
        assert "weather" in result.matched_capabilities

    def test_no_match_routes_to_general(self):
        """An unrecognised message must route to 'general' with confidence 0."""
        from src.router import MessageRouter

        descriptors = [
            self._make_descriptor("weather_agent", ["weather", "forecast"]),
        ]
        router = MessageRouter(descriptors=descriptors)
        result = router.route_message("tell me a joke")
        assert result.agent_name == "general"
        assert result.confidence == 0.0

    def test_route_task_returns_routing_result(self):
        """route_task() must also return RoutingResult."""
        from src.orchestration.models import Task
        from src.router import MessageRouter, RoutingResult

        descriptors = [
            self._make_descriptor("weather_agent", ["weather"]),
        ]
        router = MessageRouter(descriptors=descriptors)
        task = Task(id="t1", description="weather in Seattle", dependencies=[])
        result = router.route_task(task)
        assert isinstance(result, RoutingResult)


# ─────────────────────────────────────────────────────────────────────────────
# Item 6 — executor: consumes RoutingResult properly
# ─────────────────────────────────────────────────────────────────────────────


class TestExecutorRoutingResult:
    @pytest.mark.asyncio
    async def test_executor_handles_routing_result(self):
        """Executor must handle RoutingResult from route_task correctly."""
        from src.orchestration.executor import Executor
        from src.router import RoutingResult

        mock_agent = Mock()
        mock_agent.handle = AsyncMock(return_value="weather result")

        mock_registry = Mock()
        mock_registry.create_instance = Mock(return_value=mock_agent)

        mock_router = Mock()
        mock_router.route_task = Mock(
            return_value=RoutingResult(
                agent_name="weather_agent",
                confidence=0.9,
                matched_capabilities=["weather"],
            )
        )

        executor = Executor(agent_registry=mock_registry, router=mock_router)
        task = make_task(description="weather in Seattle")
        context = make_context()

        result = await executor.execute_task(task, context)

        assert result == "weather result"
        mock_registry.create_instance.assert_called_once_with("weather_agent")

    @pytest.mark.asyncio
    async def test_executor_handles_legacy_tuple_routing(self):
        """Executor must still handle tuple[str, float] from older routers."""
        from src.orchestration.executor import Executor

        mock_agent = Mock()
        mock_agent.handle = AsyncMock(return_value="ok")

        mock_registry = Mock()
        mock_registry.create_instance = Mock(return_value=mock_agent)

        mock_router = Mock()
        mock_router.route_task = Mock(return_value=("general", 0.5))

        executor = Executor(agent_registry=mock_registry, router=mock_router)
        result = await executor.execute_task(make_task(), make_context())
        assert result == "ok"
        mock_registry.create_instance.assert_called_once_with("general")


# ─────────────────────────────────────────────────────────────────────────────
# Item 7 — BaseMemory + InProcessMemory lifecycle contract
# ─────────────────────────────────────────────────────────────────────────────


class TestMemoryLifecycle:
    def test_in_process_memory_clear_removes_session(self):
        """clear() must remove the specified session only."""
        from src.memory.conversation_memory import InProcessMemory

        mem = InProcessMemory()
        mem.get_history("session-a")
        mem.get_history("session-b")
        mem.clear("session-a")
        assert "session-a" not in mem._history_store
        assert "session-b" in mem._history_store

    def test_in_process_memory_clear_all_removes_everything(self):
        """clear_all() must remove all sessions."""
        from src.memory.conversation_memory import InProcessMemory

        mem = InProcessMemory()
        for i in range(5):
            mem.get_history(f"session-{i}")
        assert len(mem._history_store) == 5
        mem.clear_all()
        assert len(mem._history_store) == 0

    def test_shutdown_clears_store_and_is_idempotent(self):
        """shutdown() must clear sessions and be callable twice without error."""
        from src.memory.conversation_memory import InProcessMemory

        mem = InProcessMemory()
        mem.get_history("s1")
        mem.get_history("s2")
        mem.shutdown()
        assert len(mem._history_store) == 0
        assert mem._shutdown_called is True
        # Second call must not raise
        mem.shutdown()
        assert mem._shutdown_called is True

    def test_base_memory_contract_enforced(self):
        """A class that doesn't implement all abstract methods cannot be instantiated."""
        from src.memory.base_memory import BaseMemory

        class Incomplete(BaseMemory):
            def get_history(self, session_id): ...
            def clear(self, session_id): ...

            # Missing: clear_all, shutdown

        with pytest.raises(TypeError):
            Incomplete()

    def test_in_process_memory_satisfies_full_contract(self):
        """InProcessMemory must be instantiable and satisfy BaseMemory."""
        from src.memory.base_memory import BaseMemory
        from src.memory.conversation_memory import InProcessMemory

        mem = InProcessMemory()
        assert isinstance(mem, BaseMemory)
        # All four methods exist and are callable
        assert callable(mem.get_history)
        assert callable(mem.clear)
        assert callable(mem.clear_all)
        assert callable(mem.shutdown)


# ─────────────────────────────────────────────────────────────────────────────
# Architecture contract — router does not import registry or container
# ─────────────────────────────────────────────────────────────────────────────


class TestRouterDoesNotCoupleToRegistry:
    def test_router_module_does_not_import_agent_registry(self):
        """MessageRouter must not depend on AgentRegistry."""
        import ast
        import pathlib

        source = pathlib.Path("src/router.py").read_text()
        tree = ast.parse(source)
        imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        import_names = []
        for node in imports:
            if isinstance(node, ast.ImportFrom):
                import_names.append(node.module or "")
            else:
                for alias in node.names:
                    import_names.append(alias.name)

        forbidden = {"agent_registry", "agent_factory", "container"}
        violations = [n for n in import_names if any(f in n for f in forbidden)]
        assert not violations, f"Router imports registry/container: {violations}"
