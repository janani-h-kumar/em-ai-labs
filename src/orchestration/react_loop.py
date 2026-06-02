"""
ReACT orchestration loop.
"""

import logging

from src.orchestration.task_graph import TaskGraph

logger = logging.getLogger(__name__)


class ReACTLoop:
    """
    Iterative reasoning and execution loop.

    Initial implementation is intentionally lightweight.
    """

    def __init__(
        self,
        planner,
        executor,
    ):
        self.planner = planner
        self.executor = executor

    async def run(
        self,
        provider,
        goal,
        context,
        max_iterations: int = 5,
    ):
        """
        Execute iterative reasoning loop.
        """
        tasks = await self.planner.create_plan(provider, goal, context)
        graph = TaskGraph(tasks)
        final_results = []

        iteration = 0
        while not graph.all_completed() and iteration < max_iterations:
            ready = graph.get_ready_tasks()
            if not ready:
                break

            if len(ready) == 1:
                result = await self.executor.execute_task(ready[0], context)
                graph.mark_completed(ready[0].id, result)
            else:
                results = await self.executor.execute_parallel(ready, context)
                for task, result in zip(ready, results, strict=True):
                    graph.mark_completed(task.id, result)

            final_results.extend([t.result for t in ready])
            iteration += 1

        return final_results
