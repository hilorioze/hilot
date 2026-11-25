from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

from .text import RichText

AccountId = NewType("AccountId", int)
ChatId = NewType("ChatId", int)
MessageId = NewType("MessageId", int)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceMessage:
    account_id: AccountId
    chat_id: ChatId
    message_id: MessageId

    # as written, without formatting
    text: str

    is_private: bool
    is_saved_messages: bool

    # reactions in saved messages are tags available only with premium
    def allows_reactions(self) -> bool:
        return not self.is_saved_messages

    def shows_progress(self) -> bool:
        return self.is_private and self.allows_reactions()

    def reports_failures(self) -> bool:
        return self.is_private


# a message holds its media, or telegram copies it into a reply when the replied message is in a chat the account can't open
@dataclass(frozen=True, slots=True, kw_only=True)
class MediaLocation:
    chat_id: ChatId
    message_id: MessageId

    is_external_reply: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Link:
    url: str

    # the link as written in the message text and its utf-16 offset, to quote it in replies
    text: str
    offset: int

    # the preview of the message plays the link's video on every client by itself
    has_video_preview: bool


class AnswerKind(StrEnum):
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerEntry:
    kind: AnswerKind
    text: RichText


# what a command did, which goes under the command so that its text stays in sight; a command over several links can both succeed and fail
@dataclass(frozen=True, slots=True, kw_only=True)
class CommandAnswer:
    entries: list[AnswerEntry]
