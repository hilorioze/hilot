from typing import Protocol

from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.value_objects.media import MediaKey


class StoredFileRepository(Protocol):
    async def get(self, media_key: MediaKey) -> StoredFile | None: ...

    async def save(self, stored_file: StoredFile) -> None: ...
