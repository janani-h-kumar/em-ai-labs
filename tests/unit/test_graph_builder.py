import asyncio

from src.orchestration.graph_builder import GraphBuilder, HumanApprovalRequiredError
from src.orchestration.models import ExecutionContext, Task


class DummyProvider:
    def chat_completion(self, *args, **kwargs):
        return "ok"


class DummyPlanner:
    async def create_plan(self, provider, goal, context):
        return [Task(id="task-1", description="demo task", assigned_agent="dummy")]


class DummyExecutor:
    async def execute_task(self, task, context):
        return {"task_id": task.id}


def test_graph_builder_state_shape_and_build():
    builder = GraphBuilder(planner=DummyPlanner(), executor=DummyExecutor())
    graph = builder.build()
    compiled = builder.compile()

    assert graph is not None
    assert compiled is not None
    assert hasattr(compiled, "ainvoke")


def test_graph_builder_checkpoint_factory_uses_sqlite_saver():
    builder = GraphBuilder(planner=DummyPlanner(), executor=DummyExecutor())
    graph, checker = builder.build_with_checkpoint(db_path=":memory:")

    assert graph is not None
    assert checker is not None


def test_graph_builder_can_execute_via_async_graph_entrypoint():
    builder = GraphBuilder(planner=DummyPlanner(), executor=DummyExecutor())
    context = ExecutionContext(session_id="sess-1", goal="demo goal")

    result = asyncio.run(
        builder.ainvoke(
            {
                "session_id": "sess-1",
                "context": context,
                "goal": "demo goal",
                "provider": DummyProvider(),
                "timeline": [],
            }
        )
    )

    assert result["plan"][0]["id"] == "task-1"
    assert result["plan"][0]["dependencies"] == []
    assert result["results"][0]["task_id"] == "task-1"
    assert result["results"][0]["result"] == {"task_id": "task-1"}
    assert any(event["event_type"] == "graph.planner.completed" for event in result["timeline"])
    assert any(event["event_type"] == "graph.executor.completed" for event in result["timeline"])


def test_graph_builder_approval_point_is_opt_in():
    builder = GraphBuilder(
        planner=DummyPlanner(),
        executor=DummyExecutor(),
        approval_enabled=True,
    )
    context = ExecutionContext(session_id="sess-1", goal="demo goal")

    try:
        asyncio.run(
            builder.ainvoke(
                {
                    "session_id": "sess-1",
                    "context": context,
                    "goal": "demo goal",
                    "provider": DummyProvider(),
                    "timeline": [],
                }
            )
        )
        assert False, "Expected HumanApprovalRequiredError"
    except HumanApprovalRequiredError as exc:
        assert "approval" in str(exc).lower()
