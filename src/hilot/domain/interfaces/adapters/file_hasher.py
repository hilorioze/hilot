from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.media import ContentHash


class FileHasher(Protocol):
    async def hash_file(self, path: Path) -> ContentHash: ...
