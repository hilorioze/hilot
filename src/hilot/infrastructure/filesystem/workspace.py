import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import override

from hilot.domain.interfaces.adapters.workspace import Workspace


class TemporaryWorkspace(Workspace):
    @override
    @asynccontextmanager
    async def create(self) -> AsyncGenerator[Path]:
        with tempfile.TemporaryDirectory(prefix="hilot-") as directory:
            yield Path(directory)
