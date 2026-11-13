import asyncio
from typing import ClassVar, cast, override

from pyrogram import Client, types
from pyrogram.raw.base.input_dialog_peer import InputDialogPeer as BaseInputDialogPeer
from pyrogram.raw.functions.messages.get_peer_dialogs import GetPeerDialogs
from pyrogram.raw.functions.users.get_full_user import GetFullUser
from pyrogram.raw.types.input_dialog_peer import InputDialogPeer
from pyrogram.raw.types.input_peer_user import InputPeerUser
from pyrogram.raw.types.input_user import InputUser
from pyrogram.raw.types.messages.peer_dialogs import PeerDialogs
from pyrogram.raw.types.users.user_full import UserFull

from hilot.domain.errors.messenger import ButtonNotFoundError
from hilot.domain.interfaces.adapters.chat_bot import ChatBot
from hilot.domain.value_objects.message import MessageId


class KurigramChatBot(ChatBot):
    _REPLY_ATTEMPTS: ClassVar[int] = 30
    _REPLY_INTERVAL: ClassVar[float] = 1

    def __init__(self, *, client: Client) -> None:
        self._client: Client = client

    @override
    async def is_used(self, bot: str) -> bool:
        # a bot is always an `InputPeerUser`; kurigram returns `None` only for a `None` peer id
        peer: InputPeerUser = cast(InputPeerUser, await self._client.resolve_peer(bot))
        dialog_peers: list[BaseInputDialogPeer] = [InputDialogPeer(peer=peer)]

        dialogs: PeerDialogs = await self._client.invoke(GetPeerDialogs(peers=dialog_peers))
        user: UserFull = await self._client.invoke(
            GetFullUser(id=InputUser(user_id=peer.user_id, access_hash=peer.access_hash))
        )

        # telegram answers with an empty dialog for a bot the account has never started
        return bool(dialogs.messages) and not user.full_user.blocked

    @override
    async def send_command(self, *, bot: str, command: str) -> MessageId:
        # kurigram returns `None` only for a scheduled message
        message: types.Message = cast(
            types.Message, await self._client.send_message(chat_id=bot, text=command)
        )

        return MessageId(message.id)

    @override
    async def press_button(self, *, bot: str, after: MessageId, data: str) -> str:
        message: types.Message = await self._wait_for_button(bot=bot, after=after, data=data)

        answer = await self._client.request_callback_answer(
            chat_id=bot, message_id=message.id, callback_data=data
        )

        return answer.message or ""

    @override
    async def read_messages(self, bot: str) -> None:
        await self._client.read_chat_history(bot)

    async def _wait_for_button(self, *, bot: str, after: MessageId, data: str) -> types.Message:
        for _ in range(self._REPLY_ATTEMPTS):
            async for message in self._client.get_chat_history(bot, limit=5):
                if message.id <= after:
                    break

                if not message.outgoing and self._has_button(message=message, data=data):
                    return message

            await asyncio.sleep(self._REPLY_INTERVAL)

        raise ButtonNotFoundError

    @staticmethod
    def _has_button(*, message: types.Message, data: str) -> bool:
        if not isinstance(message.reply_markup, types.InlineKeyboardMarkup):
            return False

        return any(
            button.callback_data == data
            for row in message.reply_markup.inline_keyboard
            for button in row
        )
