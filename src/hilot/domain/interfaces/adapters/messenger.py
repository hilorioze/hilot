from pathlib import Path
from typing import Protocol

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.value_objects.media import AttachedMedia, FileId, OutgoingMedia, StoredMedia
from hilot.domain.value_objects.message import (
    AccountId,
    ChatId,
    CommandAnswer,
    Link,
    MediaLocation,
    MessageId,
    SourceMessage,
)
from hilot.domain.value_objects.rich import RichMessage
from hilot.domain.value_objects.text import RichText


class ProgressIndicator(Protocol):
    async def show_progress(self, source: SourceMessage) -> None: ...

    async def hide_progress(self, source: SourceMessage) -> None: ...


class MessageReader(Protocol):
    async def message_exists(self, source: SourceMessage) -> bool: ...


class MessageMediaReader(Protocol):
    async def read_media(self, location: MediaLocation) -> AttachedMedia | None: ...

    # the media of the album the message is in, or its own media alone
    async def read_album(self, location: MediaLocation) -> list[AttachedMedia]: ...

    async def download_media(self, *, media: AttachedMedia, directory: Path) -> Path: ...


class UploadLimitReader(Protocol):
    def get_upload_limit(self) -> int: ...


class MediaUploader(Protocol):
    async def upload_media(
        self, *, chat_id: ChatId, media: StoredMedia, path: Path, shows_progress: bool
    ) -> FileId: ...


class CaptionLimitReader(Protocol):
    def get_caption_limit(self) -> int: ...


class TextLimitReader(Protocol):
    def get_text_limit(self) -> int: ...


class MediaSender(Protocol):
    # an album counts its media from `first_index` among the media of its part
    async def send_media(
        self,
        *,
        source: SourceMessage,
        part: int,
        first_index: int,
        media: list[OutgoingMedia],
        reply_to: MessageId,
    ) -> list[MessageId]: ...


class RichLimitReader(Protocol):
    def get_rich_text_limit(self) -> int: ...

    def get_rich_upload_limit(self) -> int: ...


# the inline bot uploads the files of the rich messages to its chat with the account
class RichMediaUploader(Protocol):
    async def upload_rich_media(
        self, *, account_id: AccountId, media: StoredMedia | CachedFile, path: Path
    ) -> FileId: ...


# the account sends a rich message as a result of the inline bot
class RichSender(Protocol):
    async def send_rich(
        self, *, source: SourceMessage, part: int, message: RichMessage, reply_to: MessageId
    ) -> MessageId: ...


class RichReplier(Protocol):
    async def reply_rich(self, *, source: SourceMessage, message: RichMessage) -> None: ...


# the caption starts with the text of the message, which keeps its formatting
class MediaAttacher(Protocol):
    async def attach_media(self, *, source: SourceMessage, media: OutgoingMedia) -> None: ...


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


# a text too long for a message goes as a file
class TextFileReplier(Protocol):
    async def reply_text_file(self, *, source: SourceMessage, name: str, text: str) -> None: ...


# the answer goes under the owner's command, so that its text stays in sight, and in reply to a command of the other side of a private chat
class CommandAnswerer(Protocol):
    async def answer_command(self, *, source: SourceMessage, answer: CommandAnswer) -> None: ...
