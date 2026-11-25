from typing import Protocol

from hilot.domain.entities.bot_file import BotFile
from hilot.domain.value_objects.media import MediaKey


class BotFileRepository(Protocol):
    async def get(self, media_key: MediaKey) -> BotFile | None: ...

    async def save(self, bot_file: BotFile) -> None: ...
