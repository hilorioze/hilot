from typing import Any, override

from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.exceptions import NoResultError

from hilot.infrastructure.metrics import TASK_FAILURES


# taskiq's own prometheus middleware serves its metrics on a server of its own
class FailureMetricMiddleware(TaskiqMiddleware):
    @override
    def on_error(
        self, message: TaskiqMessage, result: TaskiqResult[Any], exception: BaseException
    ) -> None:
        # taskiq counts a requeued task as failed
        if not isinstance(exception, NoResultError):
            TASK_FAILURES.labels(task=message.task_name).inc()
