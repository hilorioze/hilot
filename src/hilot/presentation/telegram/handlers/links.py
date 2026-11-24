from typing import cast
from urllib.parse import urlsplit

from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, MessageEntity, WebPage
from pyrogram.types.messages_and_media.message import Str

from hilot.application.media.request_download import RequestDownload, RequestDownloadDTO
from hilot.domain.value_objects.download import DownloadTrigger
from hilot.domain.value_objects.message import AccountId, Link, MessageId
from hilot.presentation.telegram.filters import COMMAND, BotChatFilter
from hilot.presentation.telegram.parsing import parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()

_LINK_TYPES: set[MessageEntityType] = {MessageEntityType.URL, MessageEntityType.TEXT_LINK}


def _parse_links(message: Message) -> list[Link]:
    # the text of a media message is its caption
    text: Str | None = cast(Str | None, message.text or message.caption)
    entities: list[MessageEntity] = message.entities or message.caption_entities or []
    video_preview_url: str | None = _get_video_preview_url(message)
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
        links.setdefault(
            url,
            Link(
                url=url,
                text=link_text,
                offset=entity.offset,
                has_video_preview=url == video_preview_url,
            ),
        )

    return list(links.values())


def _get_video_preview_url(message: Message) -> str | None:
    web_page: WebPage | None = message.web_page

    # a message previews one link, and only an enlarged preview plays its video on every client: telegram desktop opens the site from a small one
    if (
        web_page is None
        or not web_page.prefer_large_media
        or (web_page.video is None and web_page.animation is None)
    ):
        return None

    return web_page.url


# telegram finds links written without a scheme too
def _add_scheme(url: str) -> str:
    return url if urlsplit(url).netloc else f"https://{url}"


# the command goes before the links, as only the first matching handler runs
@router.on_message(filters.outgoing & filters.command(["dl", "download"], prefixes="."))
async def request_download_by_command(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestDownload],
    account_id: FromDishka[AccountId],
) -> None:
    links: list[Link] = _parse_links(message)
    reply: Message | None = message.reply_to_message

    # a command with links of its own is answered like a link, one in reply takes the place of its links' media
    if links or reply is None:
        dto: RequestDownloadDTO = RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.COMMAND if links else DownloadTrigger.REPLY_COMMAND,
            links=links,
            reply_to=MessageId(message.id),
        )
    else:
        dto = RequestDownloadDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=DownloadTrigger.REPLY_COMMAND,
            links=_parse_links(reply),
            reply_to=MessageId(reply.id),
        )

    await interactor(dto)


# a command with a link is for the hilot of its sender
@router.on_message(
    filters.text & ~COMMAND & ~BotChatFilter() & (filters.outgoing | filters.private)
)
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
