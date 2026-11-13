from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.media import StorageKey


class FileStorage(Protocol):
    async def upload(self, path: Path) -> StorageKey: ...

    async def download(self, *, key: StorageKey, path: Path) -> None: ...

    async def delete(self, key: StorageKey) -> None: ...
