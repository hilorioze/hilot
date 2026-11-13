from typing import Protocol

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.value_objects.media import MediaKey
from hilot.domain.value_objects.message import AccountId


class CachedFileRepository(Protocol):
    async def get(self, *, account_id: AccountId, media_key: MediaKey) -> CachedFile | None: ...

    async def save(self, cached_file: CachedFile) -> None: ...

    async def delete(self, cached_file: CachedFile) -> None: ...
