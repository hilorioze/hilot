from datetime import timedelta


class DetectionQuotaExceededError(Exception):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(retry_after)

        self.retry_after: timedelta = retry_after
