"""
Task execution engine.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from opentelemetry import trace as otel_trace

from src.observability.tracing import create_span, tracer
from src.orchestration.models import ExecutionContext, Task, TaskStatus
from src.utils.logging_utils import get_correlation_id

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Legacy alias — use RoutingResult from router.py for new code."""

    agent_name: str
    confidence: float


class Executor:
    """Executes orchestration tasks with OTel instrumentation."""

    def __init__(self, agent_registry, router) -> None:
        self.agent_registry = agent_registry
        self.router = router

    async def execute_task(self, task: Task, context: ExecutionContext):
        """Execute a single task."""
        with tracer.start_as_current_span("executor.execute_task") as span:
            span.set_attribute("task.id", task.id)
            span.set_attribute("task.description", task.description[:200])
            span.set_attribute("session.id", context.session_id)
            correlation_id: str | None = get_correlation_id()
            if isinstance(correlation_id, str) and correlation_id:
                span.set_attribute("correlation.id", correlation_id)

            start_time = time.perf_counter()

            logger.info(
                "Executing task",
                extra={"extra_data": {"task_id": task.id, "description": task.description}},
            )

            task.status = TaskStatus.RUNNING

            try:
                agent_name = task.assigned_agent

                if not agent_name:
                    # route_task now returns RoutingResult — extract agent_name
                    # and carry full routing metadata into the span for observability.
                    routing = self.router.route_task(task)

                    # Support both RoutingResult (new) and tuple[str,float] (old)
                    if hasattr(routing, "agent_name"):
                        agent_name = routing.agent_name
                        span.set_attribute("routing.confidence", routing.confidence)
                        matched = getattr(routing, "matched_capabilities", [])
                        if matched:
                            span.set_attribute("routing.matched_capabilities", str(matched))
                    elif isinstance(routing, tuple):
                        agent_name = routing[0]
                        span.set_attribute("routing.confidence", routing[1])
                    else:
                        agent_name = str(routing)

                resolved_agent_name: str = agent_name or ""
                span.set_attribute("agent.name", resolved_agent_name)
                span.set_attribute("agent", resolved_agent_name)
                span.set_attribute("decision", "route_to_agent")

                agent = self.agent_registry.create_instance(agent_name)

                with create_span(
                    "agent.handle",
                    agent_name=resolved_agent_name,
                    task_id=task.id,
                    session_id=context.session_id,
                ) as agent_span:
                    result = await agent.handle(task, context)
                    agent_latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                    agent_span.set_attribute("agent_latency_ms", agent_latency_ms)

                task.status = TaskStatus.COMPLETED
                task.result = result
                context.completed_tasks[task.id] = result

                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("task.status", "completed")

                logger.info(
                    "Task execution completed",
                    extra={
                        "extra_data": {
                            "task_id": task.id,
                            "agent_name": agent_name,
                            "duration_ms": duration_ms,
                        }
                    },
                )

                return result

            except Exception as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("task.status", "failed")
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))

                logger.exception(
                    "Task execution failed",
                    extra={"extra_data": {"task_id": task.id, "duration_ms": duration_ms}},
                )

                task.status = TaskStatus.FAILED
                raise

    async def execute_parallel(self, tasks: list[Task], context: ExecutionContext):
        """Execute tasks concurrently."""
        return await asyncio.gather(*[self.execute_task(task, context) for task in tasks])
