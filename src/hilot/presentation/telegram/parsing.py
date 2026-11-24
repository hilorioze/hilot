from typing import cast

from pyrogram.enums import ChatType
from pyrogram.types import Chat, Message

from hilot.domain.value_objects.message import AccountId, ChatId, MessageId, SourceMessage


def parse_source(*, message: Message, account_id: AccountId) -> SourceMessage:
    # kurigram types every field as optional, telegram sends each message with its chat
    chat: Chat = cast(Chat, message.chat)

    return SourceMessage(
        account_id=account_id,
        chat_id=ChatId(cast(int, chat.id)),
        message_id=MessageId(message.id),
        is_private=chat.type == ChatType.PRIVATE,
        is_saved_messages=chat.id == account_id,
    )
