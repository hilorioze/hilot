from typing import cast

from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Chat, Message

from hilot.application.media.request_download import RequestDownload, RequestDownloadDTO
from hilot.domain.value_objects.download import DownloadTrigger
from hilot.domain.value_objects.message import AccountId, Link, MessageId
from hilot.presentation.telegram.filters import CALLER, COMMAND, BotChatFilter
from hilot.presentation.telegram.parsing import (
    parse_external_reply_links,
    parse_links,
    parse_source,
)
from hilot.presentation.telegram.router import Router

router: Router = Router()


# the command goes before the links, as only the first matching handler runs
@router.on_message(CALLER & filters.command(["dl", "download"], prefixes="."))
async def request_download_by_command(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestDownload],
    account_id: FromDishka[AccountId],
) -> None:
    links: list[Link] = parse_links(message)
    reply: Message | None = message.reply_to_message

    # a command with links of its own gets their media in reply, one in reply gets its links' media in reply to their message
    if links or (reply is None and message.external_reply is None):
        dto: RequestDownloadDTO = RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.COMMAND,
            links=links,
            reply_to=MessageId(message.id),
        )
    elif reply is not None:
        dto = RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.COMMAND,
            links=parse_links(reply),
            # the media stays in the chat of the command, where a message replied to from another chat isn't
            reply_to=MessageId(
                reply.id
                if cast(Chat, reply.chat).id == cast(Chat, message.chat).id
                else message.id
            ),
        )
    # the replied message of an external reply is out of reach, so the media replies to the command
    else:
        dto = RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.COMMAND,
            links=parse_external_reply_links(message),
            reply_to=MessageId(message.id),
        )

    await interactor(dto)


# the commands of other userbots take links too
@router.on_message(filters.text & ~COMMAND & ~BotChatFilter() & (filters.me | filters.private))
async def request_download(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestDownload],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.LINK,
            links=parse_links(message),
            reply_to=MessageId(message.id),
        )
    )
