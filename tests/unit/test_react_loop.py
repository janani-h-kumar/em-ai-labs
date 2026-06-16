from unittest.mock import AsyncMock, Mock

import pytest

from src.orchestration.models import ExecutionContext, Task
from src.orchestration.react_loop import ReACTLoop


class SimplePlanner:
    async def create_plan(self, provider, goal, context):
        return [
            Task(id="task1", description="first", dependencies=[]),
            Task(id="task2", description="second", dependencies=["task1"]),
        ]


class SimpleExecutor:
    def __init__(self):
        self.execute_task = AsyncMock(side_effect=lambda task, context: f"result_{task.id}")
        self.execute_parallel = AsyncMock()


@pytest.mark.asyncio
async def test_react_loop_uses_reasoning_interval_and_max_tokens():
    provider = Mock()
    provider.chat_completion.return_value = "reasoning output"

    planner = SimplePlanner()
    executor = SimpleExecutor()
    react_loop = ReACTLoop(planner=planner, executor=executor)

    context = ExecutionContext(session_id="session-123", goal="Test goal")

    results = await react_loop.run(
        provider=provider,
        goal="Test goal",
        context=context,
        max_iterations=5,
        reasoning_interval=2,
        max_reasoning_tokens=16,
    )

    assert results == ["result_task1", "result_task2"]
    assert provider.chat_completion.call_count == 1
    assert provider.chat_completion.call_args.kwargs["max_tokens"] == 16

    assert context.metadata["react"]["iter_1"]["reasoning"][1] == "reasoning output"
    assert (
        context.metadata["react"]["iter_2"]["reasoning"][-1]
        == "Reasoning skipped due to interval gating."
    )
