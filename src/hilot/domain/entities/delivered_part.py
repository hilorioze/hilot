from dataclasses import dataclass, field

from hilot.domain.value_objects.message import AccountId, ChatId, MessageId


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveredPart:
    account_id: AccountId
    chat_id: ChatId
    message_id: MessageId

    part: int

    # the message holding each media of the part, none for a failure
    message_ids: list[MessageId] = field(compare=False)
