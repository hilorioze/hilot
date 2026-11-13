from contextlib import AbstractAsyncContextManager
from typing import Protocol


class DiskSpace(Protocol):
    def reserve(self, size: int) -> AbstractAsyncContextManager[None]: ...
