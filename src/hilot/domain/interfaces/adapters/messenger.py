from pathlib import Path
from typing import Protocol

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.value_objects.media import AttachedMedia, FileId, StoredMedia
from hilot.domain.value_objects.message import (
    ChatId,
    CommandAnswer,
    Link,
    MessageId,
    SourceMessage,
)


class ProgressIndicator(Protocol):
    async def show_progress(self, source: SourceMessage) -> None: ...

    async def hide_progress(self, source: SourceMessage) -> None: ...


class MessageReader(Protocol):
    async def message_exists(self, source: SourceMessage) -> bool: ...


class MessageMediaReader(Protocol):
    async def read_media(
        self, *, chat_id: ChatId, message_id: MessageId
    ) -> AttachedMedia | None: ...

    async def download_media(self, *, media: AttachedMedia, directory: Path) -> Path: ...


class UploadLimitReader(Protocol):
    def get_upload_limit(self) -> int: ...


class MediaUploader(Protocol):
    async def upload_media(
        self, *, chat_id: ChatId, media: StoredMedia, path: Path, shows_progress: bool
    ) -> FileId: ...


class MediaSender(Protocol):
    async def send_media(
        self, *, source: SourceMessage, part: int, files: list[FileId], reply_to: MessageId
    ) -> list[MessageId]: ...


class MediaRefresher(Protocol):
    async def refresh_media(self, cached_file: CachedFile) -> FileId: ...


class TextSender(Protocol):
    async def send_text(
        self, *, source: SourceMessage, part: int, text: str, quote: Link | None
    ) -> None: ...


class TextEditor(Protocol):
    async def edit_text(self, *, source: SourceMessage, text: str) -> None: ...


# the answer goes under the command, which shows that the owner called it
class CommandAnswerer(Protocol):
    async def answer_command(self, *, source: SourceMessage, answer: CommandAnswer) -> None: ...
