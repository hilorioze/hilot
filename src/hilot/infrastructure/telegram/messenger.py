import asyncio
import io
import mimetypes
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, ClassVar, cast, override

from pyrogram import Client, types
from pyrogram.enums import MessageMediaType
from pyrogram.errors import (
    ChannelPrivate,
    FileReferenceExpired,
    MessageNotModified,
    RandomIdDuplicate,
    ReactionInvalid,
)
from pyrogram.file_id import FileId as DecodedFileId
from pyrogram.file_id import FileType
from pyrogram.raw.base.document_attribute import DocumentAttribute
from pyrogram.raw.base.input_file import InputFile
from pyrogram.raw.base.input_media import InputMedia
from pyrogram.raw.base.input_peer import InputPeer
from pyrogram.raw.base.message_entity import MessageEntity
from pyrogram.raw.base.message_media import MessageMedia
from pyrogram.raw.functions.messages.edit_message import EditMessage
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
from pyrogram.raw.types.message import Message as RawMessage
from pyrogram.raw.types.message_entity_blockquote import MessageEntityBlockquote
from pyrogram.raw.types.message_entity_bold import MessageEntityBold
from pyrogram.raw.types.message_entity_text_url import MessageEntityTextUrl
from pyrogram.raw.types.message_media_document import MessageMediaDocument
from pyrogram.raw.types.message_media_photo import MessageMediaPhoto
from pyrogram.raw.types.message_media_web_page import MessageMediaWebPage
from pyrogram.raw.types.photo import Photo
from pyrogram.raw.types.send_message_upload_document_action import (
    SendMessageUploadDocumentAction,
)
from pyrogram.raw.types.send_message_upload_photo_action import SendMessageUploadPhotoAction
from pyrogram.raw.types.send_message_upload_video_action import SendMessageUploadVideoAction
from pyrogram.raw.types.update_message_id import UpdateMessageID
from pyrogram.raw.types.updates_t import Updates
from pyrogram.raw.types.web_page_pending import WebPagePending
from pyrogram.utils import get_input_media_from_file_id, get_raw_peer_id

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.errors.messenger import (
    AlreadySentError,
    FileReferenceExpiredError,
    MessageGoneError,
)
from hilot.domain.interfaces.adapters.messenger import (
    CaptionLimitReader,
    LinkPreviewReader,
    MediaAttacher,
    MediaRefresher,
    MediaSender,
    MediaUploader,
    MessageLinkReader,
    MessageMediaReader,
    MessageReader,
    ProgressIndicator,
    TextEditor,
    TextFileReplier,
    TextLimitReader,
    TextReplier,
    TextSender,
    UploadLimitReader,
)
from hilot.domain.value_objects.media import (
    AttachedMedia,
    FileId,
    MediaKind,
    OutgoingMedia,
    StoredMedia,
)
from hilot.domain.value_objects.message import (
    ChatId,
    Link,
    LinkPreview,
    MediaLocation,
    MessageId,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText, TextStyle

from .random_id import ANSWER_PART, get_random_id


class KurigramMessenger(
    ProgressIndicator,
    MessageReader,
    LinkPreviewReader,
    MessageMediaReader,
    UploadLimitReader,
    CaptionLimitReader,
    TextLimitReader,
    MediaUploader,
    MediaSender,
    MediaAttacher,
    MediaRefresher,
    TextSender,
    MessageLinkReader,
    TextEditor,
    TextReplier,
    TextFileReplier,
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

    _UNKNOWN_MIME_TYPE: ClassVar[str] = "application/octet-stream"

    # telegram shows a chat action for about 5 seconds, so it's repeated while the upload lasts
    _UPLOAD_ACTION_INTERVAL: ClassVar[float] = 4

    def __init__(self, *, client: Client) -> None:
        self._client: Client = client

    @override
    async def show_progress(self, source: SourceMessage) -> None:
        # the owner can put the reaction on or take it off from another client, and telegram refuses an unchanged one;
        # a group can leave the reaction out of the ones it allows
        with suppress(MessageNotModified, ReactionInvalid):
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
    async def read_link_preview(self, source: SourceMessage) -> LinkPreview | None:
        message: types.Message = await self._get_message(
            chat_id=source.chat_id, message_id=source.message_id
        )
        web_page: types.WebPage | None = message.web_page

        if web_page is None:
            return None

        return LinkPreview(
            url=web_page.url,
            # kurigram parses a preview telegram still builds as one without media
            is_pending=isinstance(cast(MessageMediaWebPage, web_page.raw).webpage, WebPagePending),
            plays_video=bool(web_page.prefer_large_media)
            and (web_page.video is not None or web_page.animation is not None),
        )

    @override
    async def read_media(self, location: MediaLocation) -> AttachedMedia | None:
        message: types.Message = await self._get_message(
            chat_id=location.chat_id, message_id=location.message_id
        )
        holder: types.Message | types.ExternalReplyInfo | None = (
            message.external_reply if location.is_external_reply else message
        )

        if holder is None or holder.media is None:
            return None

        # the media types are named like the attributes holding them, the same on a message and an external reply, and a poll or a location has no file
        media: Any = getattr(holder, holder.media.value)

        if getattr(media, "file_id", None) is None:
            return None

        return AttachedMedia(
            file_id=FileId(media.file_id),
            # telegram keeps every photo as a jpeg, so it has no type of its own
            mime_type="image/jpeg"
            if holder.media == MessageMediaType.PHOTO
            else media.mime_type or self._UNKNOWN_MIME_TYPE,
            size=media.file_size,
        )

    @override
    async def download_media(self, *, media: AttachedMedia, directory: Path) -> Path:
        return Path(
            cast(
                str,
                await self._client.download_media(media.file_id, file_name=directory / "media"),
            )
        )

    @override
    def get_upload_limit(self) -> int:
        # the limit kurigram's `save_file` checks against
        return (4000 if self._client.me and self._client.me.is_premium else 2000) * 1024 * 1024

    @override
    def get_caption_limit(self) -> int:
        # `caption_length_limit_default` and `caption_length_limit_premium` of telegram's app config
        return 4096 if self._client.me and self._client.me.is_premium else 1024

    @override
    def get_text_limit(self) -> int:
        # `message_length_max` of telegram's app config, the same with premium
        return 4096

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
        self,
        *,
        source: SourceMessage,
        part: int,
        first_index: int,
        media: list[OutgoingMedia],
        reply_to: MessageId,
    ) -> list[MessageId]:
        random_ids: list[int] = [
            get_random_id(source=source, part=part, index=index)
            for index in range(first_index, first_index + len(media))
        ]

        query: SendMedia | SendMultiMedia = await self._create_media_query(
            chat_id=source.chat_id, media=media, random_ids=random_ids, reply_to=reply_to
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
    async def attach_media(self, *, source: SourceMessage, media: OutgoingMedia) -> None:
        message: RawMessage = cast(
            RawMessage,
            (await self._get_message(chat_id=source.chat_id, message_id=source.message_id)).raw,
        )

        # a redelivered media finds itself already in place
        if message.media is not None and not isinstance(message.media, MessageMediaWebPage):
            raise AlreadySentError

        caption: RichText = cast(RichText, media.caption)

        with self._translate_errors():
            await self._client.invoke(
                EditMessage(
                    peer=await self._resolve_peer(source.chat_id),
                    id=source.message_id,
                    media=get_input_media_from_file_id(media.file_id),
                    message=caption.get_text(),
                    # the text of the message keeps its own formatting at the start of the caption
                    entities=[*(message.entities or []), *(self._create_entities(caption) or [])]
                    or None,
                )
            )

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
                    random_id=get_random_id(source=source, part=part, index=0),
                    reply_to=self._create_reply_to(message_id=source.message_id, quote=quote),
                    silent=True,
                )
            )

    # `t.me/c/` names a supergroup or a channel by its id without `-100`; the clients open no message of the other chats by it
    @override
    def get_message_link(self, *, chat_id: ChatId, message_id: MessageId) -> str:
        return f"https://t.me/c/{get_raw_peer_id(chat_id)}/{message_id}"

    @override
    async def edit_text(self, *, source: SourceMessage, text: RichText) -> None:
        # the text of a media message is its caption; a redelivered answer finds its text already in place
        with suppress(MessageNotModified):
            # kurigram's `edit_message_text` drops the entities it is given
            await self._client.invoke(
                EditMessage(
                    peer=await self._resolve_peer(source.chat_id),
                    id=source.message_id,
                    message=text.get_text(),
                    entities=self._create_entities(text),
                )
            )

    @override
    async def reply_text(self, *, source: SourceMessage, text: RichText) -> None:
        # a redelivered answer finds itself already sent
        with suppress(RandomIdDuplicate):
            await self._client.invoke(
                SendMessage(
                    peer=await self._resolve_peer(source.chat_id),
                    message=text.get_text(),
                    random_id=get_random_id(source=source, part=ANSWER_PART, index=0),
                    reply_to=self._create_reply_to(message_id=source.message_id, quote=None),
                    entities=self._create_entities(text),
                    silent=True,
                )
            )

    @override
    async def reply_text_file(self, *, source: SourceMessage, name: str, text: str) -> None:
        file: io.BytesIO = io.BytesIO(text.encode())
        file.name = name

        # a redelivered answer finds itself already sent
        with suppress(RandomIdDuplicate):
            await self._client.invoke(
                SendMedia(
                    peer=await self._resolve_peer(source.chat_id),
                    media=InputMediaUploadedDocument(
                        file=cast(InputFile, await self._client.save_file(file)),
                        mime_type="text/plain",
                        attributes=[DocumentAttributeFilename(file_name=name)],
                    ),
                    message="",
                    random_id=get_random_id(source=source, part=ANSWER_PART, index=0),
                    reply_to=self._create_reply_to(message_id=source.message_id, quote=None),
                    silent=True,
                )
            )

    @classmethod
    def _create_entities(cls, text: RichText) -> list[MessageEntity] | None:
        entities: list[MessageEntity] = []
        # consecutive parts with a style share one entity, which starts at the first of them
        openings: dict[TextStyle, int] = {}
        offset: int = 0

        # telegram measures the entities in utf-16 code units
        for part in text.parts:
            length: int = len(part.text.encode("utf-16-le")) // 2

            if part.url is not None:
                entities.append(MessageEntityTextUrl(offset=offset, length=length, url=part.url))

            for style in openings.keys() - part.styles:
                entities.append(
                    cls._create_style_entity(
                        style=style, offset=openings[style], length=offset - openings[style]
                    )
                )
                del openings[style]

            for style in part.styles - openings.keys():
                openings[style] = offset

            offset += length

        entities.extend(
            cls._create_style_entity(style=style, offset=start, length=offset - start)
            for style, start in openings.items()
        )
        entities.sort(key=lambda entity: entity.offset)

        # telegram refuses an empty list as `INPUT_REQUEST_TOO_LONG`
        return entities or None

    @staticmethod
    def _create_style_entity(*, style: TextStyle, offset: int, length: int) -> MessageEntity:
        if style == TextStyle.BOLD:
            return MessageEntityBold(offset=offset, length=length)

        return MessageEntityBlockquote(offset=offset, length=length, collapsed=True)

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
        self,
        *,
        chat_id: ChatId,
        media: list[OutgoingMedia],
        random_ids: list[int],
        reply_to: MessageId,
    ) -> SendMedia | SendMultiMedia:
        peer: InputPeer = await self._resolve_peer(chat_id)
        input_reply_to: InputReplyToMessage = self._create_reply_to(
            message_id=reply_to, quote=None
        )

        # a lone media goes out as a plain message, as the official app sends it
        if len(media) == 1:
            return SendMedia(
                peer=peer,
                media=get_input_media_from_file_id(media[0].file_id),
                message=media[0].caption.get_text() if media[0].caption else "",
                random_id=random_ids[0],
                reply_to=input_reply_to,
                entities=self._create_entities(media[0].caption) if media[0].caption else None,
                silent=True,
            )

        return SendMultiMedia(
            peer=peer,
            multi_media=[
                InputSingleMedia(
                    media=get_input_media_from_file_id(item.file_id),
                    random_id=random_id,
                    message=item.caption.get_text() if item.caption else "",
                    entities=self._create_entities(item.caption) if item.caption else None,
                )
                for item, random_id in zip(media, random_ids, strict=True)
            ],
            reply_to=input_reply_to,
            silent=True,
        )

    @staticmethod
    def _create_reply_to(*, message_id: MessageId, quote: Link | None) -> InputReplyToMessage:
        if quote is None:
            return InputReplyToMessage(reply_to_msg_id=message_id)

        return InputReplyToMessage(
            reply_to_msg_id=message_id, quote_text=quote.text, quote_offset=quote.offset
        )

    @staticmethod
    @contextmanager
    def _translate_errors() -> Generator[None]:
        try:
            yield
        except FileReferenceExpired as error:
            raise FileReferenceExpiredError from error
        except RandomIdDuplicate as error:
            raise AlreadySentError from error
