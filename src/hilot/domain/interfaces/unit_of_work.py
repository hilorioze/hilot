from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...

    # commit on success, roll back on error
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
