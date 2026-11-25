from typing import Protocol

from hilot.domain.entities.telegram_file_hash import TelegramFileHash
from hilot.domain.value_objects.media import FileUniqueId


class TelegramFileHashRepository(Protocol):
    async def get(self, file_unique_id: FileUniqueId) -> TelegramFileHash | None: ...

    async def save(self, telegram_file_hash: TelegramFileHash) -> None: ...
