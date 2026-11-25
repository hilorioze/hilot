from typing import Protocol

from hilot.domain.entities.cached_transcript import CachedTranscript
from hilot.domain.value_objects.media import FileUniqueId


class CachedTranscriptRepository(Protocol):
    async def get(self, file_unique_id: FileUniqueId) -> CachedTranscript | None: ...

    async def save(self, cached_transcript: CachedTranscript) -> None: ...
