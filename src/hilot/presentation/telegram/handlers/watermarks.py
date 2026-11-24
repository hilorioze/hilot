from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Message

from hilot.application.watermarks.request_check import (
    RequestWatermarkCheck,
    RequestWatermarkCheckDTO,
)
from hilot.domain.value_objects.message import AccountId, MessageId
from hilot.presentation.telegram.parsing import parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()


def _get_media_message_id(message: Message) -> MessageId:
    # a command without media of its own checks the message it replies to
    if message.media is None and message.reply_to_message_id is not None:
        return MessageId(message.reply_to_message_id)

    return MessageId(message.id)


# the command checks the media it replies to, or the one it's the caption of
@router.on_message(filters.outgoing & filters.command(["synth", "synthid"], prefixes="."))
async def request_watermark_check(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestWatermarkCheck],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestWatermarkCheckDTO(
            source=parse_source(message=message, account_id=account_id),
            media_message_id=_get_media_message_id(message),
        )
    )
