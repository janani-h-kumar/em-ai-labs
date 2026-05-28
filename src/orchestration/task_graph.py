"""
Task dependency graph utilities.
"""

from src.orchestration.models import Task, TaskStatus


class TaskGraph:
    """
    Maintains orchestration task dependencies and execution state.
    """

    def __init__(self, tasks: list[Task]):
        self.tasks = {task.id: task for task in tasks}

    def get_ready_tasks(self) -> list[Task]:
        """
        Return tasks ready for execution.
        """

        ready_tasks = []

        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            dependencies_complete = all(
                self.tasks[dep].status == TaskStatus.COMPLETED for dep in task.dependencies
            )

            if dependencies_complete:
                ready_tasks.append(task)

        return ready_tasks

    def mark_completed(self, task_id: str, result):
        """
        Mark task as completed.
        """

        task = self.tasks[task_id]

        task.status = TaskStatus.COMPLETED
        task.result = result

    def mark_failed(self, task_id: str):
        """
        Mark task as failed.
        """

        task = self.tasks[task_id]

        task.status = TaskStatus.FAILED

    def all_completed(self) -> bool:
        """
        Check if all tasks completed successfully.
        """

        return all(task.status == TaskStatus.COMPLETED for task in self.tasks.values())
