from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from .text import RichText

AccountId = NewType("AccountId", int)
ChatId = NewType("ChatId", int)
MessageId = NewType("MessageId", int)


# a private chat is with a person, a chat with a bot is apart
class ChatKind(StrEnum):
    PRIVATE = "private"
    BOT = "bot"
    GROUP = "group"
    CHANNEL = "channel"


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceMessage:
    account_id: AccountId
    chat_id: ChatId
    message_id: MessageId

    # as written, without formatting
    text: str

    chat_kind: ChatKind
    is_saved_messages: bool

    # the owner's own message, which the account can edit; the other side of a private chat calls the commands too
    is_outgoing: bool

    # a link preview isn't media of the message
    has_media: bool

    sent_at: datetime

    @property
    def is_private(self) -> bool:
        return self.chat_kind == ChatKind.PRIVATE

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


# telegram builds the preview of a link it hasn't seen yet after the message is sent and puts it in by an edit
@dataclass(frozen=True, slots=True, kw_only=True)
class LinkPreview:
    # telegram may leave out the url of a preview it still builds
    url: str | None

    is_pending: bool

    # only a large preview plays its video on every client: telegram desktop opens the site from a small one
    plays_video: bool


class AnswerKind(StrEnum):
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class AnswerEntry:
    kind: AnswerKind
    text: RichText


# what a command did; a command over several links can both succeed and fail
@dataclass(frozen=True, slots=True, kw_only=True)
class CommandAnswer:
    entries: list[AnswerEntry]
