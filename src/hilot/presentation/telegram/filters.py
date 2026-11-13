from datetime import UTC, datetime, timedelta
from typing import cast, override

from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.filters import Filter
from pyrogram.raw.base.update import Update as RawUpdate
from pyrogram.types import Chat, Message, Update


# the messages caught up on after a downtime longer than `max_age` are left alone
class RecentFilter(Filter):
    def __init__(self, max_age: timedelta) -> None:
        self._max_age: timedelta = max_age

    @override
    async def __call__(self, _: Client, update: Update | RawUpdate) -> bool:
        # a message handler filters only messages
        date: datetime = cast(datetime, cast(Message, update).date)

        # kurigram returns naive dates in the local time zone
        return datetime.now(UTC) - date.astimezone(UTC) <= self._max_age


class BotChatFilter(Filter):
    @override
    async def __call__(self, _: Client, update: Update | RawUpdate) -> bool:
        # telegram sends each message with its chat
        return cast(Chat, cast(Message, update).chat).type == ChatType.BOT
