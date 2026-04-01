"""Tests for background task infrastructure (baky.tasks helpers)."""

from unittest.mock import MagicMock, patch

from baky.tasks import on_task_error, queue_task


class TestQueueTask:
    @patch("baky.tasks.async_task")
    def test_queue_task_returns_task_id(self, mock_async):
        mock_async.return_value = "abc-123"
        result = queue_task("apps.reports.tasks.generate_report", 42)
        assert result == "abc-123"

    @patch("baky.tasks.async_task")
    def test_queue_task_passes_func_path_and_args(self, mock_async):
        mock_async.return_value = "id-1"
        queue_task("apps.reports.tasks.generate_report", 42)
        mock_async.assert_called_once_with(
            "apps.reports.tasks.generate_report",
            42,
            task_name="generate_report",
        )

    @patch("baky.tasks.async_task")
    def test_queue_task_uses_custom_task_name(self, mock_async):
        mock_async.return_value = "id-2"
        queue_task("apps.reports.tasks.generate_report", 42, task_name="custom_name")
        mock_async.assert_called_once_with(
            "apps.reports.tasks.generate_report",
            42,
            task_name="custom_name",
        )

    @patch("baky.tasks.async_task")
    def test_queue_task_forwards_extra_kwargs(self, mock_async):
        mock_async.return_value = "id-3"
        queue_task("apps.reports.tasks.generate_report", 42, hook="baky.tasks.on_task_error", group="reports")
        mock_async.assert_called_once_with(
            "apps.reports.tasks.generate_report",
            42,
            task_name="generate_report",
            hook="baky.tasks.on_task_error",
            group="reports",
        )

    @patch("baky.tasks.async_task")
    def test_queue_task_with_no_args(self, mock_async):
        mock_async.return_value = "id-4"
        result = queue_task("some.module.task_func")
        assert result == "id-4"
        mock_async.assert_called_once_with("some.module.task_func", task_name="task_func")


class TestOnTaskError:
    def test_logs_failure_details(self, caplog):
        task = MagicMock()
        task.name = "generate_report"
        task.id = "fail-id-1"
        task.result = "ConnectionError: database unavailable"

        with caplog.at_level("ERROR", logger="baky.tasks"):
            on_task_error(task)

        assert "generate_report" in caplog.text
        assert "fail-id-1" in caplog.text
        assert "ConnectionError" in caplog.text
