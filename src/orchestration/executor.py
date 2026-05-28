"""
Task execution engine.
"""

import asyncio
import logging
from dataclasses import dataclass

from src.orchestration.models import ExecutionContext, Task, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    agent_name: str
    confidence: float


class Executor:
    """
    Executes orchestration tasks.
    """

    def __init__(
        self,
        agent_registry,
        router,
    ):
        self.agent_registry = agent_registry
        self.router = router

    async def execute_task(
        self,
        task: Task,
        context: ExecutionContext,
    ):
        """
        Execute a single task.
        """

        logger.info(
            "Executing task",
            extra={
                "extra_data": {
                    "task_id": task.id,
                    "description": task.description,
                }
            },
        )

        task.status = TaskStatus.RUNNING

        try:
            agent_name = task.assigned_agent

            if not agent_name:
                agent_name = self.router.route_task(task)

            agent = self.agent_registry.get(agent_name)

            result = await agent.handle(
                task,
                context,
            )

            task.status = TaskStatus.COMPLETED
            task.result = result

            context.completed_tasks[task.id] = result

            return result

        except Exception as e:
            logger.exception(
                "Task execution failed",
                extra={
                    "extra_data": {
                        "task_id": task.id,
                    }
                },
            )

            task.status = TaskStatus.FAILED

            raise e

    async def execute_parallel(
        self,
        tasks: list[Task],
        context: ExecutionContext,
    ):
        """
        Execute tasks concurrently.
        """

        return await asyncio.gather(*[self.execute_task(task, context) for task in tasks])
