"""
ReACT orchestration loop.
"""

import logging

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
        goal,
        context,
        max_iterations: int = 5,
    ):
        """
        Execute iterative reasoning loop.
        """

        logger.info(
            "Starting ReACT loop",
            extra={
                "extra_data": {
                    "goal": goal,
                    "session_id": context.session_id,
                }
            },
        )

        iteration = 0

        final_results = []

        while iteration < max_iterations:
            tasks = await self.planner.create_plan(
                goal,
                context,
            )

            if not tasks:
                break

            for task in tasks:
                result = await self.executor.execute_task(
                    task,
                    context,
                )

                final_results.append(result)

            # Initial implementation:
            # stop after first successful execution cycle
            break

        return final_results
