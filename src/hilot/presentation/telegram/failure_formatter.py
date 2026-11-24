from typing import ClassVar, override

from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.value_objects.download import Failure, FailureReason


class ChatFailureFormatter(FailureFormatter):
    _TEXTS: ClassVar[dict[FailureReason, str]] = {
        FailureReason.LOGIN_REQUIRED: "it's private or needs a login",
        FailureReason.GEO_RESTRICTED: "not available in my region",
        FailureReason.UNAVAILABLE: "couldn't download it",
        FailureReason.BUG: "something broke on my side",
    }

    @override
    def format_failure(self, *, failure: Failure, size_limit: int) -> str:
        if failure.reason != FailureReason.TOO_BIG:
            return self._TEXTS[failure.reason]

        if failure.size is None:
            return f"too big, limit is {self._format_size(size_limit)}"

        return (
            f"too big: {self._format_size(failure.size)}, limit is {self._format_size(size_limit)}"
        )

    @override
    def format_failures(self, *, failures: list[Failure], size_limit: int) -> str:
        if len(failures) == 1:
            return self.format_failure(failure=failures[0], size_limit=size_limit)

        # several failures go into one message, each after its link
        return "\n".join(
            f"{failure.link.text}: {self.format_failure(failure=failure, size_limit=size_limit)}"
            for failure in failures
        )

    @override
    def format_no_links(self) -> str:
        return "nothing to download, add a link or reply to one"

    @staticmethod
    def _format_size(size: int) -> str:
        return f"{round(size / 1024**3, 1):g} GB"
