from prometheus_client import Counter

EXTRACTIONS: Counter = Counter("hilot_extractions", "links an extractor took", ["extractor"])
LOGIN_REQUIRED: Counter = Counter(
    "hilot_login_required", "extractions refused without a login", ["extractor"]
)
MEDIA_UNAVAILABLE: Counter = Counter(
    "hilot_media_unavailable", "links and media an extractor failed to get", ["extractor"]
)
TASK_FAILURES: Counter = Counter("hilot_task_failures", "tasks that raised an error", ["task"])
