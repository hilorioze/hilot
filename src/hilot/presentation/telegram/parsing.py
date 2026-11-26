from typing import cast
from urllib.parse import urlsplit

from pyrogram.enums import ChatType, MessageEntityType, MessageMediaType
from pyrogram.types import (
    Chat,
    ExternalReplyInfo,
    LinkPreviewOptions,
    Message,
    MessageEntity,
    TextQuote,
)
from pyrogram.types.messages_and_media.message import Str

from hilot.domain.value_objects.message import (
    AccountId,
    ChatId,
    ChatKind,
    Link,
    MediaLocation,
    MessageId,
    SourceMessage,
)

_CHAT_KINDS: dict[ChatType, ChatKind] = {
    ChatType.PRIVATE: ChatKind.PRIVATE,
    ChatType.BOT: ChatKind.BOT,
    ChatType.GROUP: ChatKind.GROUP,
    ChatType.SUPERGROUP: ChatKind.GROUP,
    ChatType.FORUM: ChatKind.GROUP,
    # the direct messages of a channel are a group of their own
    ChatType.DIRECT: ChatKind.GROUP,
    ChatType.CHANNEL: ChatKind.CHANNEL,
}

_LINK_TYPES: set[MessageEntityType] = {MessageEntityType.URL, MessageEntityType.TEXT_LINK}


# the messages with a text or a caption
_TEXT_MEDIA: set[MessageMediaType | None] = {
    None,
    MessageMediaType.WEB_PAGE,
    MessageMediaType.PHOTO,
    MessageMediaType.VIDEO,
    MessageMediaType.AUDIO,
    MessageMediaType.DOCUMENT,
    MessageMediaType.ANIMATION,
    MessageMediaType.VOICE,
}


def parse_source(*, message: Message, account_id: AccountId) -> SourceMessage:
    # kurigram types every field as optional, telegram sends each message with its chat
    chat: Chat = cast(Chat, message.chat)

    is_saved_messages: bool = chat.id == account_id

    return SourceMessage(
        account_id=account_id,
        chat_id=ChatId(cast(int, chat.id)),
        message_id=MessageId(message.id),
        # the text of a media message is its caption
        text=str(message.text or message.caption or ""),
        chat_kind=_CHAT_KINDS[cast(ChatType, chat.type)],
        is_saved_messages=is_saved_messages,
        # telegram marks the messages of saved messages incoming, and a forwarded one can't be edited
        is_outgoing=bool(message.outgoing)
        or (is_saved_messages and message.forward_origin is None),
        has_media=message.media not in {None, MessageMediaType.WEB_PAGE},
        takes_text=message.media in _TEXT_MEDIA,
    )


# a command takes the media of its own message, of the one it replies to, or the one telegram copies into a reply from another chat
def parse_media_location(message: Message) -> MediaLocation:
    # kurigram types every field as optional, telegram sends each message with its chat
    own: MediaLocation = MediaLocation(
        chat_id=ChatId(cast(int, cast(Chat, message.chat).id)),
        message_id=MessageId(message.id),
        is_external_reply=False,
    )
    reply: Message | None = message.reply_to_message

    if message.media is not None:
        return own

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


def parse_links(message: Message) -> list[Link]:
    # the text of a media message is its caption
    return _find_links(
        text=cast(Str | None, message.text or message.caption),
        entities=message.entities or message.caption_entities or [],
    )


# a reply to a message in a chat the account can't open carries only the part of its text the reply quotes and the link of its preview
def parse_external_reply_links(message: Message) -> list[Link]:
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


# the links of the message a command replies to, or of the one telegram copies into a reply from another chat
def parse_reply_links(message: Message) -> list[Link]:
    reply: Message | None = message.reply_to_message

    if reply is not None:
        return parse_links(reply)

    if message.external_reply is not None:
        return parse_external_reply_links(message)

    return []
