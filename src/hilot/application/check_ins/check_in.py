import asyncio
import random
from dataclasses import dataclass

from hilot.domain.interfaces.adapters.chat_bot import ChatBot
from hilot.domain.value_objects.check_in import CheckIn
from hilot.domain.value_objects.message import MessageId

# random pauses between the presses hide the automation from the bot
_MIN_PAUSE: float = 2
_MAX_PAUSE: float = 8


@dataclass(frozen=True, slots=True, kw_only=True)
class RunCheckInDTO:
    check_in: CheckIn


class RunCheckIn:
    def __init__(self, *, chat_bot: ChatBot) -> None:
        self._chat_bot: ChatBot = chat_bot

    async def __call__(self, data: RunCheckInDTO) -> str | None:
        # skip a bot the account has never started or has blocked
        if not await self._chat_bot.is_used(data.check_in.bot):
            return None

        message_id: MessageId = await self._chat_bot.send_command(
            bot=data.check_in.bot, command=data.check_in.command
        )
        answer: str = ""

        for button in data.check_in.buttons:
            await asyncio.sleep(random.uniform(_MIN_PAUSE, _MAX_PAUSE))  # noqa: S311  # a pause, not a secret

            answer = await self._chat_bot.press_button(
                bot=data.check_in.bot, after=message_id, data=button
            )

        # don't leave unread replies in the chat
        await self._chat_bot.read_messages(data.check_in.bot)

        return answer
