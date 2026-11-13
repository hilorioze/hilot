from prometheus_client import Counter

LOGIN_REQUIRED: Counter = Counter(
    "hilot_login_required", "extractions refused without a login", ["extractor"]
)
TASK_FAILURES: Counter = Counter("hilot_task_failures", "tasks that raised an error", ["task"])
