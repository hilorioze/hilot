from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Message

from hilot.application.watermarks.request_check import (
    RequestWatermarkCheck,
    RequestWatermarkCheckDTO,
)
from hilot.domain.value_objects.message import AccountId
from hilot.presentation.telegram.filters import CALLER
from hilot.presentation.telegram.parsing import parse_media_location, parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()


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
            media_location=parse_media_location(message),
        )
    )
