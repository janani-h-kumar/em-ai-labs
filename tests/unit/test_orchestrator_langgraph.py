from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.guardrails import GuardrailConfig
from src.guardrails.exceptions import GuardrailViolationError
from src.orchestration.orchestrator import Orchestrator


class DictConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value


def make_history():
    history = MagicMock()
    history.messages = []
    return history


def make_orchestrator(config=None):
    memory = MagicMock()
    memory.get_history.return_value = make_history()

    orch = Orchestrator(
        agent_registry=Mock(),
        router=Mock(),
        provider=Mock(),
        memory=memory,
        guardrail_config=GuardrailConfig(),
        config_manager=config,
    )
    return orch


@pytest.mark.asyncio
async def test_default_runtime_still_uses_react_loop():
    orch = make_orchestrator()
    orch.react_loop.run = AsyncMock(return_value=["react result"])
    orch.graph_builder.ainvoke = AsyncMock(return_value={})

    response = await orch.run("hello", "session-1")

    assert response == "react result"
    orch.react_loop.run.assert_awaited_once()
    orch.graph_builder.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_langgraph_runtime_calls_graph_builder():
    config = DictConfig({"runtime": {"orchestration": "langgraph"}})
    orch = make_orchestrator(config)
    orch.react_loop.run = AsyncMock(return_value=["react result"])
    orch.graph_builder.ainvoke = AsyncMock(
        return_value={
            "results": [{"task_id": "task-1", "result": "graph result"}],
            "timeline": [],
        }
    )

    response = await orch.run("hello", "session-2")

    assert response == "graph result"
    orch.graph_builder.ainvoke.assert_awaited_once()
    orch.react_loop.run.assert_not_called()


@pytest.mark.asyncio
async def test_langgraph_failure_surfaces_by_default():
    config = DictConfig({"runtime": {"orchestration": "langgraph"}})
    orch = make_orchestrator(config)
    orch.graph_builder.ainvoke = AsyncMock(side_effect=RuntimeError("graph broke"))
    orch.react_loop.run = AsyncMock(return_value=["react result"])

    with pytest.raises(RuntimeError, match="graph broke"):
        await orch.run("hello", "session-3")

    orch.react_loop.run.assert_not_called()


@pytest.mark.asyncio
async def test_langgraph_failure_can_fallback_to_react():
    config = DictConfig(
        {"runtime": {"orchestration": "langgraph", "langgraph": {"fallback_to_react": True}}}
    )
    orch = make_orchestrator(config)
    orch.graph_builder.ainvoke = AsyncMock(side_effect=RuntimeError("graph broke"))
    orch.react_loop.run = AsyncMock(return_value=["react fallback"])

    response = await orch.run("hello", "session-4")

    assert response == "react fallback"
    orch.react_loop.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_langgraph_empty_result_still_hits_output_guardrail():
    config = DictConfig({"runtime": {"orchestration": "langgraph"}})
    orch = make_orchestrator(config)
    orch.graph_builder.ainvoke = AsyncMock(return_value={"results": [], "timeline": []})

    with pytest.raises(GuardrailViolationError):
        await orch.run("hello", "session-5")
