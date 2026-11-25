import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from html import escape
from itertools import groupby
from pathlib import Path
from typing import ClassVar, cast, override

from aiogram import Bot
from aiogram.exceptions import AiogramError, TelegramForbiddenError
from aiogram.types import (
    Audio,
    FSInputFile,
    InlineQueryResultArticle,
    InputMediaAudio,
    InputMediaPhoto,
    InputMediaVideo,
    InputRichMessage,
    InputRichMessageContent,
    InputRichMessageMedia,
    Message,
    PhotoSize,
    Video,
)
from aiogram.types import PreparedInlineMessage as BotPreparedInlineMessage
from pyrogram import Client
from pyrogram.errors import ChatSendInlineForbidden
from pyrogram.raw.base.input_peer import InputPeer
from pyrogram.raw.functions.messages.get_prepared_inline_message import (
    GetPreparedInlineMessage,
)
from pyrogram.raw.functions.messages.send_inline_bot_result import SendInlineBotResult
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.input_reply_to_message import InputReplyToMessage
from pyrogram.raw.types.input_user import InputUser
from pyrogram.raw.types.messages.prepared_inline_message import PreparedInlineMessage
from pyrogram.raw.types.update_message_id import UpdateMessageID
from pyrogram.raw.types.updates_t import Updates

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.errors.messenger import RichUnavailableError
from hilot.domain.interfaces.adapters.messenger import (
    RichLimitReader,
    RichMediaUploader,
    RichReplier,
    RichSender,
)
from hilot.domain.value_objects.media import FileId, MediaKind, StoredMedia
from hilot.domain.value_objects.message import AccountId, ChatKind, MessageId, SourceMessage
from hilot.domain.value_objects.rich import RichMedia, RichMessage
from hilot.domain.value_objects.text import RichText, TextPart, TextStyle

from .random_id import ANSWER_PART, get_random_id

_logger: logging.Logger = logging.getLogger(__name__)


# the account sends plainly whatever keeps the bot from a rich message
@contextmanager
def _fall_back_to_plain() -> Generator[None]:
    try:
        yield
    # the bot can't message an account that hasn't started it
    except TelegramForbiddenError as error:
        raise RichUnavailableError from error
    except AiogramError as error:
        _logger.exception("the inline bot failed to make a rich message")

        raise RichUnavailableError from error


class InlineBotRichMessenger(RichLimitReader, RichMediaUploader, RichSender, RichReplier):
    # the html tags of the media blocks of a rich message
    _MEDIA_TAGS: ClassVar[dict[MediaKind, str]] = {
        MediaKind.PHOTO: "img",
        MediaKind.VIDEO: "video",
        MediaKind.AUDIO: "audio",
    }

    # a collage lays out up to an album's 10 media at once, a slideshow shows more one by one
    _COLLAGE_SIZE: ClassVar[int] = 10

    # the line breaks around a paragraph, which separate the blocks of a plain message
    _EDGE_BREAKS: ClassVar[re.Pattern[str]] = re.compile(r"^(?:<br/>)+|(?:<br/>)+$")

    # the inline result only carries the message, telegram shows neither its id nor its title
    _RESULT_ID: ClassVar[str] = "rich"

    def __init__(self, *, bot: Bot, client: Client, local_mode: bool) -> None:
        self._bot: Bot = bot
        self._client: Client = client
        self._local_mode: bool = local_mode

    @override
    def get_rich_text_limit(self) -> int:
        return 32768

    @override
    def get_rich_upload_limit(self) -> int:
        return (2000 if self._local_mode else 50) * 1024 * 1024

    # the message is deleted at once: only its file is needed
    @override
    async def upload_rich_media(
        self, *, account_id: AccountId, media: StoredMedia | CachedFile, path: Path
    ) -> FileId:
        file: FSInputFile = FSInputFile(path)

        with _fall_back_to_plain():
            message: Message = await self._send_file(account_id=account_id, media=media, file=file)
            await self._bot.delete_message(chat_id=account_id, message_id=message.message_id)

        # a photo comes in several sizes, the largest one last
        match media.kind:
            case MediaKind.PHOTO:
                return FileId(cast(list[PhotoSize], message.photo)[-1].file_id)
            case MediaKind.VIDEO:
                return FileId(cast(Video, message.video).file_id)
            case MediaKind.AUDIO:
                return FileId(cast(Audio, message.audio).file_id)

    @override
    async def send_rich(
        self, *, source: SourceMessage, part: int, message: RichMessage, reply_to: MessageId
    ) -> MessageId:
        random_id: int = get_random_id(source=source, part=part, index=0)
        updates: Updates = await self._send(
            source=source, message=message, random_id=random_id, reply_to=reply_to
        )

        # telegram answers a repeated random id with the message it sent before
        return next(
            MessageId(update.id)
            for update in updates.updates
            if isinstance(update, UpdateMessageID) and update.random_id == random_id
        )

    @override
    async def reply_rich(self, *, source: SourceMessage, message: RichMessage) -> None:
        # a redelivered answer gets the message sent before
        await self._send(
            source=source,
            message=message,
            random_id=get_random_id(source=source, part=ANSWER_PART, index=0),
            reply_to=source.message_id,
        )

    async def _send_file(
        self, *, account_id: AccountId, media: StoredMedia | CachedFile, file: FSInputFile
    ) -> Message:
        match media.kind:
            case MediaKind.PHOTO:
                return await self._bot.send_photo(
                    chat_id=account_id, photo=file, disable_notification=True
                )
            case MediaKind.VIDEO:
                return await self._bot.send_video(
                    chat_id=account_id,
                    video=file,
                    duration=round(media.info.duration) if media.info.duration else None,
                    width=media.info.width,
                    height=media.info.height,
                    supports_streaming=True,
                    disable_notification=True,
                )
            case MediaKind.AUDIO:
                return await self._bot.send_audio(
                    chat_id=account_id,
                    audio=file,
                    duration=round(media.info.duration) if media.info.duration else None,
                    # a cached file keeps no title or performer
                    title=media.title if isinstance(media, StoredMedia) else None,
                    performer=media.performer if isinstance(media, StoredMedia) else None,
                    disable_notification=True,
                )

    # the bot prepares the message for the account, which sends it as the bot's inline result
    async def _send(
        self, *, source: SourceMessage, message: RichMessage, random_id: int, reply_to: MessageId
    ) -> Updates:
        prepared: PreparedInlineMessage = await self._prepare(source=source, message=message)

        try:
            # telegram answers a sent message with the full updates
            return cast(
                Updates,
                await self._client.invoke(
                    SendInlineBotResult(
                        # kurigram returns `None` only for a `None` peer id
                        peer=cast(InputPeer, await self._client.resolve_peer(source.chat_id)),
                        random_id=random_id,
                        query_id=prepared.query_id,
                        id=prepared.result.id,
                        reply_to=InputReplyToMessage(reply_to_msg_id=reply_to),
                        silent=True,
                    )
                ),
            )
        except ChatSendInlineForbidden as error:
            raise RichUnavailableError from error

    # kurigram misreads a message prepared for several types of chats, so it's prepared for the type it goes to
    async def _prepare(
        self, *, source: SourceMessage, message: RichMessage
    ) -> PreparedInlineMessage:
        with _fall_back_to_plain():
            prepared: BotPreparedInlineMessage = await self._bot.save_prepared_inline_message(
                user_id=source.account_id,
                result=InlineQueryResultArticle(
                    id=self._RESULT_ID,
                    title=self._RESULT_ID,
                    input_message_content=InputRichMessageContent(
                        rich_message=self._create_rich_message(message)
                    ),
                ),
                allow_user_chats=source.chat_kind == ChatKind.PRIVATE,
                allow_bot_chats=source.chat_kind == ChatKind.BOT,
                allow_group_chats=source.chat_kind == ChatKind.GROUP,
                allow_channel_chats=source.chat_kind == ChatKind.CHANNEL,
            )
            bot_user: InputUser = await self._get_bot_user()

        return await self._client.invoke(GetPreparedInlineMessage(bot=bot_user, id=prepared.id))

    async def _get_bot_user(self) -> InputUser:
        peer: InputPeerUser = cast(
            InputPeerUser,
            await self._client.resolve_peer(cast(str, (await self._bot.me()).username)),
        )

        return InputUser(user_id=peer.user_id, access_hash=peer.access_hash)

    @classmethod
    def _create_rich_message(cls, message: RichMessage) -> InputRichMessage:
        media_ids: list[str] = [f"media{index}" for index in range(len(message.media))]
        blocks: list[str] = [
            f'<{cls._MEDIA_TAGS[media.kind]} src="tg://{media.kind.value}?id={media_id}"/>'
            for media, media_id in zip(message.media, media_ids, strict=True)
        ]

        # the audio go one under another
        if len(blocks) > 1 and message.media[0].kind != MediaKind.AUDIO:
            tag: str = "tg-collage" if len(blocks) <= cls._COLLAGE_SIZE else "tg-slideshow"
            blocks = [f"<{tag}>{''.join(blocks)}</{tag}>"]

        return InputRichMessage(
            html="".join([*blocks, *((cls._render_text(message.text),) if message.text else ())]),
            media=[
                InputRichMessageMedia(id=media_id, media=cls._create_input_media(media))
                for media, media_id in zip(message.media, media_ids, strict=True)
            ]
            or None,
        )

    @staticmethod
    def _create_input_media(
        media: RichMedia,
    ) -> InputMediaPhoto | InputMediaVideo | InputMediaAudio:
        match media.kind:
            case MediaKind.PHOTO:
                return InputMediaPhoto(media=media.file_id)
            case MediaKind.VIDEO:
                return InputMediaVideo(media=media.file_id)
            case MediaKind.AUDIO:
                return InputMediaAudio(media=media.file_id)

    # an expandable quote is a block of its own, the text between the quotes goes in paragraphs
    @classmethod
    def _render_text(cls, text: RichText) -> str:
        blocks: list[str] = []

        for is_quote, group in groupby(
            text.parts, key=lambda part: TextStyle.EXPANDABLE_QUOTE in part.styles
        ):
            parts: list[TextPart] = list(group)
            html: str = "".join(cls._render_part(part) for part in parts)

            if is_quote:
                blocks.append(f"<blockquote expandable>{html}</blockquote>")
            elif "".join(part.text for part in parts).strip():
                blocks.append(f"<p>{cls._EDGE_BREAKS.sub('', html)}</p>")

        return "".join(blocks)

    @staticmethod
    def _render_part(part: TextPart) -> str:
        html: str = escape(part.text).replace("\n", "<br/>")

        if TextStyle.BOLD in part.styles:
            html = f"<b>{html}</b>"

        if part.url is not None:
            html = f'<a href="{escape(part.url)}">{html}</a>'

        return html
