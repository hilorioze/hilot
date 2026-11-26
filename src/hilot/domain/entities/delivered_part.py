from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from hilot.domain.value_objects.message import AccountId, ChatId, MessageId


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveredPart:
    # a delivery repeated after a crash or a gone cached file comes within minutes, so a day is spare
    _LIFETIME: ClassVar[timedelta] = timedelta(days=1)

    account_id: AccountId
    chat_id: ChatId
    message_id: MessageId

    part: int

    # the message holding each media of the part, none for a failure
    message_ids: list[MessageId] = field(compare=False)

    delivered_at: datetime = field(compare=False)

    def get_expiry(self) -> datetime:
        return self.delivered_at + self._LIFETIME
