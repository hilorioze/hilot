from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Message

from hilot.application.watermarks.request_check import (
    RequestWatermarkCheck,
    RequestWatermarkCheckDTO,
)
from hilot.domain.value_objects.message import AccountId, Link
from hilot.presentation.telegram.filters import CALLER
from hilot.presentation.telegram.parsing import (
    parse_links,
    parse_media_location,
    parse_reply_links,
    parse_source,
)
from hilot.presentation.telegram.router import Router

router: Router = Router()


# the command checks the media of its own links, or the media it replies to or is the caption of, or else the media of the links it replies to
@router.on_message(CALLER & filters.command(["synth", "synthid"], prefixes="."))
async def request_watermark_check(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestWatermarkCheck],
    account_id: FromDishka[AccountId],
) -> None:
    links: list[Link] = parse_links(message)

    await interactor(
        RequestWatermarkCheckDTO(
            source=parse_source(message=message, account_id=account_id),
            media_location=None if links else parse_media_location(message),
            links=links or parse_reply_links(message),
        )
    )
