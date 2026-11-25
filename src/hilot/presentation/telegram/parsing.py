from datetime import UTC, datetime
from typing import cast

from pyrogram.enums import ChatType, MessageMediaType
from pyrogram.types import Chat, Message

from hilot.domain.value_objects.message import (
    AccountId,
    ChatId,
    MessageId,
    SourceMessage,
)


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
        is_private=chat.type == ChatType.PRIVATE,
        is_saved_messages=is_saved_messages,
        # telegram marks the messages of saved messages incoming, and a forwarded one can't be edited
        is_outgoing=bool(message.outgoing)
        or (is_saved_messages and message.forward_origin is None),
        has_media=message.media not in {None, MessageMediaType.WEB_PAGE},
        # kurigram returns naive dates in the local time zone
        sent_at=cast(datetime, message.date).astimezone(UTC),
    )
