from dataclasses import dataclass
from typing import NewType

AccountId = NewType("AccountId", int)
ChatId = NewType("ChatId", int)
MessageId = NewType("MessageId", int)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceMessage:
    account_id: AccountId
    chat_id: ChatId
    message_id: MessageId

    is_private: bool
    is_saved_messages: bool

    # reactions in saved messages are tags available only with premium
    def shows_progress(self) -> bool:
        return self.is_private and not self.is_saved_messages

    def reports_failures(self) -> bool:
        return self.is_private


@dataclass(frozen=True, slots=True, kw_only=True)
class Link:
    url: str

    # the link as written in the message text and its utf-16 offset, to quote it in replies
    text: str
    offset: int

    # the preview of the message plays the link's video on every client by itself
    has_video_preview: bool
