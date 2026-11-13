from typing import Protocol

from hilot.domain.value_objects.download import Failure


class FailureFormatter(Protocol):
    def format_failure(self, *, failure: Failure, size_limit: int) -> str: ...
