import asyncio
import hashlib
import mimetypes
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import ClassVar, cast, override

from pyrogram import Client, types
from pyrogram.errors import (
    ChannelPrivate,
    FileReferenceExpired,
    MessageNotModified,
    RandomIdDuplicate,
)
from pyrogram.file_id import FileId as DecodedFileId
from pyrogram.file_id import FileType
from pyrogram.raw.base.document_attribute import DocumentAttribute
from pyrogram.raw.base.input_file import InputFile
from pyrogram.raw.base.input_media import InputMedia
from pyrogram.raw.base.input_peer import InputPeer
from pyrogram.raw.base.message_media import MessageMedia
from pyrogram.raw.functions.messages.send_media import SendMedia
from pyrogram.raw.functions.messages.send_message import SendMessage
from pyrogram.raw.functions.messages.send_multi_media import SendMultiMedia
from pyrogram.raw.functions.messages.set_typing import SetTyping
from pyrogram.raw.functions.messages.upload_media import UploadMedia
from pyrogram.raw.types.document import Document
from pyrogram.raw.types.document_attribute_audio import DocumentAttributeAudio
from pyrogram.raw.types.document_attribute_filename import DocumentAttributeFilename
from pyrogram.raw.types.document_attribute_video import DocumentAttributeVideo
from pyrogram.raw.types.input_media_uploaded_document import InputMediaUploadedDocument
from pyrogram.raw.types.input_media_uploaded_photo import InputMediaUploadedPhoto
from pyrogram.raw.types.input_reply_to_message import InputReplyToMessage
from pyrogram.raw.types.input_single_media import InputSingleMedia
from pyrogram.raw.types.message_media_document import MessageMediaDocument
from pyrogram.raw.types.message_media_photo import MessageMediaPhoto
from pyrogram.raw.types.photo import Photo
from pyrogram.raw.types.send_message_upload_document_action import (
    SendMessageUploadDocumentAction,
)
from pyrogram.raw.types.send_message_upload_photo_action import SendMessageUploadPhotoAction
from pyrogram.raw.types.send_message_upload_video_action import SendMessageUploadVideoAction
from pyrogram.raw.types.update_message_id import UpdateMessageID
from pyrogram.raw.types.updates_t import Updates
from pyrogram.utils import get_input_media_from_file_id

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.errors.messenger import (
    AlreadySentError,
    FileReferenceExpiredError,
    MessageGoneError,
)
from hilot.domain.interfaces.adapters.messenger import (
    MediaRefresher,
    MediaSender,
    MediaUploader,
    MessageReader,
    ProgressIndicator,
    TextSender,
    UploadLimitReader,
)
from hilot.domain.value_objects.media import FileId, MediaKind, StoredMedia
from hilot.domain.value_objects.message import ChatId, Link, MessageId, SourceMessage


class KurigramMessenger(
    ProgressIndicator,
    MessageReader,
    UploadLimitReader,
    MediaUploader,
    MediaSender,
    MediaRefresher,
    TextSender,
):
    _PROGRESS_REACTION: ClassVar[str] = "👀"

    _DOCUMENT_FILE_TYPES: ClassVar[dict[MediaKind, FileType]] = {
        MediaKind.VIDEO: FileType.VIDEO,
        MediaKind.AUDIO: FileType.AUDIO,
    }

    _UPLOAD_ACTIONS: ClassVar[
        dict[
            MediaKind,
            type[
                SendMessageUploadPhotoAction
                | SendMessageUploadVideoAction
                | SendMessageUploadDocumentAction
            ],
        ]
    ] = {
        MediaKind.PHOTO: SendMessageUploadPhotoAction,
        MediaKind.VIDEO: SendMessageUploadVideoAction,
        # an official client sends audio files as documents, voice messages have their own action
        MediaKind.AUDIO: SendMessageUploadDocumentAction,
    }

    # telegram shows a chat action for about 5 seconds, so it's repeated while the upload lasts
    _UPLOAD_ACTION_INTERVAL: ClassVar[float] = 4

    def __init__(self, *, client: Client) -> None:
        self._client: Client = client

    @override
    async def show_progress(self, source: SourceMessage) -> None:
        # the owner can put the reaction on or take it off from another client, and telegram refuses an unchanged one
        with suppress(MessageNotModified):
            await self._client.send_reaction(
                chat_id=source.chat_id, message_id=source.message_id, emoji=self._PROGRESS_REACTION
            )

    @override
    async def hide_progress(self, source: SourceMessage) -> None:
        with suppress(MessageNotModified):
            await self._client.send_reaction(chat_id=source.chat_id, message_id=source.message_id)

    @override
    async def message_exists(self, source: SourceMessage) -> bool:
        try:
            await self._get_message(chat_id=source.chat_id, message_id=source.message_id)
        except MessageGoneError:
            return False

        return True

    @override
    def get_upload_limit(self) -> int:
        # the limit kurigram's `save_file` checks against
        return (4000 if self._client.me and self._client.me.is_premium else 2000) * 1024 * 1024

    @override
    async def upload_media(
        self, *, chat_id: ChatId, media: StoredMedia, path: Path, shows_progress: bool
    ) -> FileId:
        peer: InputPeer = await self._resolve_peer(chat_id)

        file: InputFile = (
            await self._save_file_showing_progress(peer=peer, kind=media.kind, path=path)
            if shows_progress
            else await self._client.save_file(path)
        )

        uploaded: MessageMedia = await self._client.invoke(
            UploadMedia(
                peer=peer, media=self._create_input_media(media=media, file=file, path=path)
            )
        )

        # telegram returns the photo or the document it was given
        if media.kind == MediaKind.PHOTO:
            photo: Photo = cast(Photo, cast(MessageMediaPhoto, uploaded).photo)

            # kurigram builds the file id of a photo from its largest size and parses it only privately
            return FileId(cast(types.Photo, types.Photo._parse(self._client, photo)).file_id)  # noqa: SLF001

        document: Document = cast(Document, cast(MessageMediaDocument, uploaded).document)

        return FileId(
            DecodedFileId(
                file_type=self._DOCUMENT_FILE_TYPES[media.kind],
                dc_id=document.dc_id,
                media_id=document.id,
                access_hash=document.access_hash,
                file_reference=document.file_reference,
            ).encode()
        )

    @override
    async def send_media(
        self, *, source: SourceMessage, part: int, files: list[FileId]
    ) -> list[MessageId]:
        random_ids: list[int] = [
            self._get_random_id(source=source, part=part, index=index)
            for index in range(len(files))
        ]

        query: SendMedia | SendMultiMedia = await self._create_media_query(
            source=source, files=files, random_ids=random_ids
        )

        with self._translate_errors():
            # telegram answers a sent media with the full updates
            updates: Updates = cast(Updates, await self._client.invoke(query))

        message_ids: dict[int, MessageId] = {
            update.random_id: MessageId(update.id)
            for update in updates.updates
            if isinstance(update, UpdateMessageID)
        }

        return [message_ids[random_id] for random_id in random_ids]

    @override
    async def refresh_media(self, cached_file: CachedFile) -> FileId:
        message: types.Message = await self._get_message(
            chat_id=cached_file.chat_id, message_id=cached_file.message_id
        )

        # the media kinds are named like the message attributes holding them
        return FileId(getattr(message, cached_file.kind.value).file_id)

    @override
    async def send_text(
        self, *, source: SourceMessage, part: int, text: str, quote: Link | None
    ) -> None:
        with self._translate_errors():
            await self._client.invoke(
                SendMessage(
                    peer=await self._resolve_peer(source.chat_id),
                    message=text,
                    random_id=self._get_random_id(source=source, part=part, index=0),
                    reply_to=self._create_reply_to(source=source, quote=quote),
                )
            )

    async def _save_file_showing_progress(
        self, *, peer: InputPeer, kind: MediaKind, path: Path
    ) -> InputFile:
        percentage: int = 0

        async def track_progress(current: int, total: int) -> None:
            nonlocal percentage
            percentage = current * 100 // total

        async def show_progress() -> None:
            while True:
                await self._client.invoke(
                    SetTyping(peer=peer, action=self._UPLOAD_ACTIONS[kind](progress=percentage))
                )
                await asyncio.sleep(self._UPLOAD_ACTION_INTERVAL)

        async with asyncio.TaskGroup() as group:
            # show the upload percentage in the chat, as an official client does, until the media replaces it
            progress_task: asyncio.Task[None] = group.create_task(show_progress())

            try:
                return await self._client.save_file(path, progress=track_progress)
            finally:
                progress_task.cancel()

    async def _get_message(self, *, chat_id: ChatId, message_id: MessageId) -> types.Message:
        try:
            message: types.Message | None = await self._client.get_messages(
                chat_id=chat_id, message_ids=message_id, replies=0
            )
        except ChannelPrivate as error:
            raise MessageGoneError from error

        if message is None or message.empty:
            raise MessageGoneError

        return message

    async def _resolve_peer(self, chat_id: ChatId) -> InputPeer:
        # kurigram returns `None` only for a `None` peer id
        return cast(InputPeer, await self._client.resolve_peer(chat_id))

    def _create_input_media(
        self, *, media: StoredMedia, file: InputFile, path: Path
    ) -> InputMedia:
        if media.kind == MediaKind.PHOTO:
            return InputMediaUploadedPhoto(file=file)

        return InputMediaUploadedDocument(
            file=file,
            mime_type=mimetypes.types_map[path.suffix],
            attributes=[
                self._create_media_attribute(media),
                DocumentAttributeFilename(file_name=media.file_name),
            ],
        )

    @staticmethod
    def _create_media_attribute(media: StoredMedia) -> DocumentAttribute:
        # 0 stands for an unknown duration or dimension, as in kurigram's `send_video`
        if media.kind == MediaKind.VIDEO:
            return DocumentAttributeVideo(
                duration=media.info.duration or 0,
                w=media.info.width or 0,
                h=media.info.height or 0,
                supports_streaming=True,
            )

        return DocumentAttributeAudio(
            duration=int(media.info.duration or 0), title=media.title, performer=media.performer
        )

    async def _create_media_query(
        self, *, source: SourceMessage, files: list[FileId], random_ids: list[int]
    ) -> SendMedia | SendMultiMedia:
        peer: InputPeer = await self._resolve_peer(source.chat_id)
        reply_to: InputReplyToMessage = self._create_reply_to(source=source, quote=None)

        # a lone media goes out as a plain message, as the official app sends it
        if len(files) == 1:
            return SendMedia(
                peer=peer,
                media=get_input_media_from_file_id(files[0]),
                message="",
                random_id=random_ids[0],
                reply_to=reply_to,
            )

        return SendMultiMedia(
            peer=peer,
            multi_media=[
                InputSingleMedia(
                    media=get_input_media_from_file_id(file_id), random_id=random_id, message=""
                )
                for file_id, random_id in zip(files, random_ids, strict=True)
            ],
            reply_to=reply_to,
        )

    @staticmethod
    def _create_reply_to(*, source: SourceMessage, quote: Link | None) -> InputReplyToMessage:
        if quote is None:
            return InputReplyToMessage(reply_to_msg_id=source.message_id)

        return InputReplyToMessage(
            reply_to_msg_id=source.message_id, quote_text=quote.text, quote_offset=quote.offset
        )

    @staticmethod
    def _get_random_id(*, source: SourceMessage, part: int, index: int) -> int:
        # the same part of a message always gets the same random ids, so telegram refuses to send it twice
        digest: bytes = hashlib.blake2b(
            f"{source.account_id}:{source.chat_id}:{source.message_id}:{part}:{index}".encode(),
            digest_size=8,
        ).digest()

        return int.from_bytes(digest, signed=True)

    @staticmethod
    @contextmanager
    def _translate_errors() -> Generator[None]:
        try:
            yield
        except FileReferenceExpired as error:
            raise FileReferenceExpiredError from error
        except RandomIdDuplicate as error:
            raise AlreadySentError from error
