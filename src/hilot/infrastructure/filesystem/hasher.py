import asyncio
import hashlib
from pathlib import Path
from typing import override

from hilot.domain.interfaces.adapters.file_hasher import FileHasher
from hilot.domain.value_objects.media import ContentHash


class Sha256FileHasher(FileHasher):
    @override
    async def hash_file(self, path: Path) -> ContentHash:
        return ContentHash(await asyncio.to_thread(self._hash_file, path))

    def _hash_file(self, path: Path) -> str:
        with path.open("rb") as file:
            return hashlib.file_digest(file, "sha256").hexdigest()
