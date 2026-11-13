from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.media import MediaKind


class MediaTranscoder(Protocol):
    async def transcode(
        self, *, path: Path, kind: MediaKind, directory: Path, size_limit: int
    ) -> Path: ...
