from typing import cast

from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Chat, Message

from hilot.application.watermarks.request_check import (
    RequestWatermarkCheck,
    RequestWatermarkCheckDTO,
)
from hilot.domain.value_objects.message import AccountId, ChatId, MediaLocation, MessageId
from hilot.presentation.telegram.filters import CALLER
from hilot.presentation.telegram.parsing import parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()


def _find_media_location(message: Message) -> MediaLocation:
    # kurigram types every field as optional, telegram sends each message with its chat
    own: MediaLocation = MediaLocation(
        chat_id=ChatId(cast(int, cast(Chat, message.chat).id)),
        message_id=MessageId(message.id),
        is_external_reply=False,
    )
    reply: Message | None = message.reply_to_message

    if message.media is not None:
        return own

    # a command without media of its own checks the message it replies to, which can be in another chat
    if reply is not None:
        return MediaLocation(
            chat_id=ChatId(cast(int, cast(Chat, reply.chat).id)),
            message_id=MessageId(reply.id),
            is_external_reply=False,
        )

    if message.external_reply is not None:
        return MediaLocation(
            chat_id=own.chat_id, message_id=own.message_id, is_external_reply=True
        )

    return own


# the command checks the media it replies to, or the one it's the caption of
@router.on_message(CALLER & filters.command(["synth", "synthid"], prefixes="."))
async def request_watermark_check(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestWatermarkCheck],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestWatermarkCheckDTO(
            source=parse_source(message=message, account_id=account_id),
            media_location=_find_media_location(message),
        )
    )
