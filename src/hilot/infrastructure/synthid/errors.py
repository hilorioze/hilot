from datetime import timedelta


class QuotaExceededError(Exception):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(retry_after)

        self.retry_after: timedelta = retry_after


# synthid answers a bad attestation or request with a status instead of a result
class DetectionRefusedError(Exception):
    def __init__(self, status: list[int] | None) -> None:
        super().__init__(status)

        self.status: list[int] | None = status
