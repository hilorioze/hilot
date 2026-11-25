from typing import Protocol

from hilot.domain.value_objects.download import Failure


class FailureFormatter(Protocol):
    def format_failure(self, *, failure: Failure, size_limit: int) -> str: ...

    def format_failures(
        self, *, failures: list[Failure], size_limit: int, names_links: bool
    ) -> list[str]: ...

    def format_no_links(self) -> str: ...

    def format_no_media(self) -> str: ...
