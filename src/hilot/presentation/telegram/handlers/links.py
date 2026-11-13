from typing import cast
from urllib.parse import urlsplit

from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.enums import ChatType, MessageEntityType
from pyrogram.types import Chat, Message, WebPage
from pyrogram.types.messages_and_media.message import Str

from hilot.application.media.request_download import RequestDownload, RequestDownloadDTO
from hilot.domain.value_objects.message import AccountId, ChatId, Link, MessageId, SourceMessage
from hilot.presentation.telegram.filters import BotChatFilter
from hilot.presentation.telegram.router import Router

router: Router = Router()

_LINK_TYPES: set[MessageEntityType] = {MessageEntityType.URL, MessageEntityType.TEXT_LINK}


def _parse_source(*, message: Message, account_id: AccountId) -> SourceMessage:
    # kurigram types every field as optional, telegram sends each message with its chat
    chat: Chat = cast(Chat, message.chat)

    return SourceMessage(
        account_id=account_id,
        chat_id=ChatId(cast(int, chat.id)),
        message_id=MessageId(message.id),
        is_private=chat.type == ChatType.PRIVATE,
        is_saved_messages=chat.id == account_id,
    )


def _parse_links(message: Message) -> list[Link]:
    # `filters.text` lets only the messages with text through
    text: Str = cast(Str, message.text)
    video_preview_url: str | None = _get_video_preview_url(message)
    links: dict[str, Link] = {}

    for entity in message.entities or []:
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


@router.on_message(filters.text & ~BotChatFilter() & (filters.outgoing | filters.private))
async def request_download(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestDownload],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestDownloadDTO(
            source=_parse_source(message=message, account_id=account_id),
            links=_parse_links(message),
        )
    )
