from typing import override

from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.bot_file import BotFile
from hilot.domain.interfaces.repositories.bot_file import BotFileRepository
from hilot.domain.value_objects.media import FileId, MediaKey
from hilot.infrastructure.database.sql.models.bot_file import BotFileModel
from hilot.infrastructure.database.sql.upsert import upsert


# the files of the configured bot, so that another bot doesn't get file ids it can't use
class SQLBotFileRepository(BotFileRepository):
    def __init__(self, *, session: AsyncSession, bot_id: int) -> None:
        self._session: AsyncSession = session
        self._bot_id: int = bot_id

    @override
    async def get(self, media_key: MediaKey) -> BotFile | None:
        model: BotFileModel | None = await self._session.get(
            BotFileModel, (self._bot_id, media_key.extractor, media_key.media_id)
        )

        if model is None:
            return None

        return BotFile(media_key=media_key, file_id=FileId(model.file_id))

    @override
    async def save(self, bot_file: BotFile) -> None:
        await upsert(
            session=self._session,
            model=BotFileModel,
            rows=[
                {
                    "bot_id": self._bot_id,
                    "extractor": bot_file.media_key.extractor,
                    "media_id": bot_file.media_key.media_id,
                    "file_id": bot_file.file_id,
                }
            ],
        )
