from datetime import UTC, datetime
from typing import cast

from pyrogram.enums import ChatType, MessageMediaType
from pyrogram.types import Chat, Message

from hilot.domain.value_objects.message import (
    AccountId,
    ChatId,
    MediaLocation,
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
