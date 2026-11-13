import shutil
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import override

from hilot.domain.errors.disk_space import NotEnoughSpaceError
from hilot.domain.interfaces.adapters.disk_space import DiskSpace


class LocalDiskSpace(DiskSpace):
    def __init__(self, *, min_free_space: int) -> None:
        self._min_free_space: int = min_free_space
        self._reserved: int = 0

    @override
    @asynccontextmanager
    async def reserve(self, size: int) -> AsyncGenerator[None]:
        # the workspaces live in the temporary directory
        # a file being written counts both in its reservation and in the used space, so the free space comes out too low, never too high
        free_space: int = shutil.disk_usage(tempfile.gettempdir()).free - self._reserved

        if free_space - size < self._min_free_space:
            raise NotEnoughSpaceError

        self._reserved += size

        try:
            yield
        finally:
            self._reserved -= size
