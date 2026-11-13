class UnsupportedLinkError(Exception):
    pass


class NoMediaError(Exception):
    pass


# a link or one of its media failed for a reason the sender is told about
class DownloadFailedError(Exception):
    pass


class LoginRequiredError(DownloadFailedError):
    pass


class GeoRestrictedError(DownloadFailedError):
    pass


class MediaUnavailableError(DownloadFailedError):
    pass


class TooBigError(DownloadFailedError):
    def __init__(self, *, size: int | None) -> None:
        super().__init__(size)

        self.size: int | None = size
