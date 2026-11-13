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

from .media import StoredMedia
from .message import Link, SourceMessage


class FailureReason(StrEnum):
    TOO_BIG = "too_big"
    LOGIN_REQUIRED = "login_required"
    GEO_RESTRICTED = "geo_restricted"
    UNAVAILABLE = "unavailable"


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


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadRequest:
    source: SourceMessage
    links: list[Link]

    size_limit: int


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
