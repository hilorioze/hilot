from datetime import timedelta


class DetectionQuotaExceededError(Exception):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(retry_after)

        self.retry_after: timedelta = retry_after


# a signed out or deleted account can't sign in again with its refresh token
class DetectionAccountRevokedError(Exception):
    pass


class NoDetectionAccountsError(Exception):
    pass
