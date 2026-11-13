from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Protocol


class Workspace(Protocol):
    def create(self) -> AbstractAsyncContextManager[Path]: ...
