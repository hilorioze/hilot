from pathlib import Path
from typing import Protocol

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.value_objects.media import AttachedMedia, FileId, OutgoingMedia, StoredMedia
from hilot.domain.value_objects.message import (
    ChatId,
    CommandAnswer,
    Link,
    LinkPreview,
    MediaLocation,
    MessageId,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText


class ProgressIndicator(Protocol):
    async def show_progress(self, source: SourceMessage) -> None: ...

    async def hide_progress(self, source: SourceMessage) -> None: ...


class MessageReader(Protocol):
    async def message_exists(self, source: SourceMessage) -> bool: ...


class LinkPreviewReader(Protocol):
    async def read_link_preview(self, source: SourceMessage) -> LinkPreview | None: ...


class MessageMediaReader(Protocol):
    async def read_media(self, location: MediaLocation) -> AttachedMedia | None: ...

    async def download_media(self, *, media: AttachedMedia, directory: Path) -> Path: ...


class UploadLimitReader(Protocol):
    def get_upload_limit(self) -> int: ...


class MediaUploader(Protocol):
    async def upload_media(
        self, *, chat_id: ChatId, media: StoredMedia, path: Path, shows_progress: bool
    ) -> FileId: ...


class CaptionLimitReader(Protocol):
    def get_caption_limit(self) -> int: ...


class MediaSender(Protocol):
    async def send_media(
        self, *, source: SourceMessage, part: int, media: list[OutgoingMedia], reply_to: MessageId
    ) -> list[MessageId]: ...


class MediaRefresher(Protocol):
    async def refresh_media(self, cached_file: CachedFile) -> FileId: ...


class TextSender(Protocol):
    async def send_text(
        self, *, source: SourceMessage, part: int, text: str, quote: Link | None
    ) -> None: ...


class MessageLinkReader(Protocol):
    def get_message_link(self, *, chat_id: ChatId, message_id: MessageId) -> str: ...


class TextEditor(Protocol):
    async def edit_text(self, *, source: SourceMessage, text: RichText) -> None: ...


class TextReplier(Protocol):
    async def reply_text(self, *, source: SourceMessage, text: RichText) -> None: ...


# the answer goes under the owner's command, so that its text stays in sight, and in reply to a command of the other side of a private chat
class CommandAnswerer(Protocol):
    async def answer_command(self, *, source: SourceMessage, answer: CommandAnswer) -> None: ...
