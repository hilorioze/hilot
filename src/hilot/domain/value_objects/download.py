from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Self

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.errors.extraction import (
    DownloadFailedError,
    GeoRestrictedError,
    LoginRequiredError,
    MediaUnavailableError,
    TooBigError,
)

from .media import MediaInfo, PostDetails, StoredMedia
from .message import ChatId, Link, MessageId, SourceMessage


class FailureReason(StrEnum):
    TOO_BIG = "too_big"
    LOGIN_REQUIRED = "login_required"
    GEO_RESTRICTED = "geo_restricted"
    UNAVAILABLE = "unavailable"
    BUG = "bug"


@dataclass(frozen=True, slots=True, kw_only=True)
class Failure:
    _REASONS: ClassVar[dict[type[DownloadFailedError], FailureReason]] = {
        TooBigError: FailureReason.TOO_BIG,
        LoginRequiredError: FailureReason.LOGIN_REQUIRED,
        GeoRestrictedError: FailureReason.GEO_RESTRICTED,
        MediaUnavailableError: FailureReason.UNAVAILABLE,
    }

    link: Link
    reason: FailureReason

    size: int | None

    @classmethod
    def from_error(cls, *, link: Link, error: DownloadFailedError) -> Self:
        return cls(
            link=link,
            reason=cls._REASONS[type(error)],
            size=error.size if isinstance(error, TooBigError) else None,
        )

    @classmethod
    def from_bug(cls, link: Link) -> Self:
        return cls(link=link, reason=FailureReason.BUG, size=None)


class DownloadTrigger(StrEnum):
    # a message with links, downloaded by itself
    LINK = "link"

    # `.dl` of the owner or of the other side of a private chat, with links of its own or in reply to a message with links
    COMMAND = "command"


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadRequest:
    # the message with the links or the command
    source: SourceMessage
    trigger: DownloadTrigger

    links: list[Link]

    # the message the media replies to
    reply_to: MessageId

    size_limit: int

    # a command is called on purpose, so unlike a link it shows progress and failures in groups too
    def is_commanded(self) -> bool:
        return self.trigger != DownloadTrigger.LINK

    def shows_progress(self) -> bool:
        return (
            self.source.allows_reactions() if self.is_commanded() else self.source.shows_progress()
        )

    def reports_failures(self) -> bool:
        return self.is_commanded() or self.source.reports_failures()

    def answers_command(self) -> bool:
        return self.is_commanded()

    # a failure among the media of several links names its link
    def names_links(self) -> bool:
        return len(self.links) > 1


# a post whose media went out, with the first message holding it
@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveredPost:
    post: PostDetails
    media: list[MediaInfo]

    chat_id: ChatId
    message_id: MessageId


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadResult:
    request: DownloadRequest

    media: list[StoredMedia | CachedFile]
    failures: list[Failure]

    def get_stored_media(self) -> list[StoredMedia]:
        return [item for item in self.media if isinstance(item, StoredMedia)]

    def needs_transcoding(self) -> bool:
        return any(media.info.needs_transcoding() for media in self.get_stored_media())

    @classmethod
    def from_items(
        cls, *, request: DownloadRequest, items: list[StoredMedia | CachedFile | Failure]
    ) -> Self:
        return cls(
            request=request,
            media=[item for item in items if not isinstance(item, Failure)],
            failures=[item for item in items if isinstance(item, Failure)],
        )
