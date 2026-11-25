from typing import cast
from urllib.parse import urlsplit

from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import (
    Chat,
    ExternalReplyInfo,
    LinkPreviewOptions,
    Message,
    MessageEntity,
    TextQuote,
)
from pyrogram.types.messages_and_media.message import Str

from hilot.application.media.request_download import RequestDownload, RequestDownloadDTO
from hilot.domain.value_objects.download import DownloadTrigger
from hilot.domain.value_objects.message import AccountId, Link, MessageId
from hilot.presentation.telegram.filters import CALLER, COMMAND, BotChatFilter
from hilot.presentation.telegram.parsing import parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()

_LINK_TYPES: set[MessageEntityType] = {MessageEntityType.URL, MessageEntityType.TEXT_LINK}


def _parse_links(message: Message) -> list[Link]:
    # the text of a media message is its caption
    return _find_links(
        text=cast(Str | None, message.text or message.caption),
        entities=message.entities or message.caption_entities or [],
    )


# a reply to a message in a chat the account can't open carries only the part of its text the reply quotes and the link of its preview
def _parse_external_reply_links(message: Message) -> list[Link]:
    quote: TextQuote | None = message.quote
    external_reply: ExternalReplyInfo = cast(ExternalReplyInfo, message.external_reply)
    preview: LinkPreviewOptions | None = external_reply.link_preview_options
    links: dict[str, Link] = {
        link.url: link
        for link in (
            _find_links(text=cast(Str | None, quote.text), entities=quote.entities or [])
            if quote is not None
            else []
        )
    }

    # the preview of a quoted link adds nothing
    if preview is not None and preview.url is not None:
        links.setdefault(preview.url, Link(url=preview.url, text=preview.url, offset=0))

    return list(links.values())


def _find_links(*, text: Str | None, entities: list[MessageEntity]) -> list[Link]:
    links: dict[str, Link] = {}

    if text is None:
        return []

    for entity in entities:
        if entity.type not in _LINK_TYPES:
            continue

        # `Str` slices by the utf-16 offsets of the entities
        link_text: str = text[entity.offset : entity.offset + entity.length]

        # only a text link carries its url apart from the text
        url: str = _add_scheme(entity.url or link_text)

        # a link mentioned twice is downloaded once, and replies quote its first mention
        links.setdefault(url, Link(url=url, text=link_text, offset=entity.offset))

    return list(links.values())


# telegram finds links written without a scheme too
def _add_scheme(url: str) -> str:
    return url if urlsplit(url).netloc else f"https://{url}"


# the command goes before the links, as only the first matching handler runs
@router.on_message(CALLER & filters.command(["dl", "download"], prefixes="."))
async def request_download_by_command(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestDownload],
    account_id: FromDishka[AccountId],
) -> None:
    links: list[Link] = _parse_links(message)
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
            links=_parse_links(reply),
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
            links=_parse_external_reply_links(message),
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
            links=_parse_links(message),
            reply_to=MessageId(message.id),
        )
    )
