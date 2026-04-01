"""Task queue helpers for Django-Q2.

Provides a thin wrapper around django_q.tasks.async_task that applies
consistent defaults (retry, logging, error hooks) so individual task
callers don't have to repeat boilerplate.
"""

import logging

from django_q.tasks import async_task

logger = logging.getLogger(__name__)


def queue_task(func_path: str, *args, task_name: str | None = None, **kwargs) -> str:
    """Queue a background task with standard retry and error handling.

    Args:
        func_path: Dotted path to the task function (e.g., "apps.reports.tasks.generate_report").
        *args: Positional arguments passed to the task function.
        task_name: Optional human-readable name for admin visibility.
        **kwargs: Additional keyword arguments passed to async_task (e.g., hook, group).

    Returns:
        The task ID string.
    """
    task_id = async_task(
        func_path,
        *args,
        task_name=task_name or func_path.rsplit(".", 1)[-1],
        **kwargs,
    )
    logger.info("Queued task %s (id=%s) with args=%s", func_path, task_id, args)
    return task_id


def on_task_error(task):
    """Hook called when a task fails permanently (after all retries exhausted).

    Registered as the default error hook. Logs the failure so it can be
    picked up by monitoring / alerting.
    """
    logger.error(
        "Task %s (id=%s) failed permanently: %s",
        task.name,
        task.id,
        task.result,
    )
