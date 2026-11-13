from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.media import MediaInfo


class MediaProber(Protocol):
    async def probe(self, path: Path) -> MediaInfo: ...
