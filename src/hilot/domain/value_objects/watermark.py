from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from itertools import groupby
from typing import Self

from .download import DownloadResult, Failure
from .media import FileUniqueId, StorageKey, StoredMedia
from .message import Link, SourceMessage


class WatermarkVerdict(StrEnum):
    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    UNDETERMINED = "undetermined"


class UndeterminedReason(StrEnum):
    EMPTY = "empty"
    LOW_RESOLUTION = "low_resolution"
    NOT_ENOUGH_DETAIL = "not_enough_detail"
    LOW_QUALITY = "low_quality"
    POSSIBLE_TAMPERING = "possible_tampering"
    LOW_FPS = "low_fps"
    TOO_LONG = "too_long"
    UNKNOWN = "unknown"


class WatermarkConfidence(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkSegment:
    # seconds from the start of the media
    start: int
    end: int

    verdict: WatermarkVerdict


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkCheck:
    verdict: WatermarkVerdict
    reason: UndeterminedReason | None

    confidence: WatermarkConfidence | None
    provider: str | None

    video_segments: list[WatermarkSegment]
    audio_segments: list[WatermarkSegment]


class WatermarkFailure(StrEnum):
    NO_MEDIA = "no_media"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    TOO_BIG = "too_big"
    BUG = "bug"


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkQuotaExceeded:
    retry_after: timedelta


# names a media among the others of the command: its link among several links, its place among several media of its link
@dataclass(frozen=True, slots=True, kw_only=True)
class MediaLabel:
    link: Link | None
    position: int | None

    # a media alone needs no name
    @classmethod
    def empty(cls) -> Self:
        return cls(link=None, position=None)


# a file the check takes
@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkTarget:
    storage_key: StorageKey
    mime_type: str
    size: int

    # the file of a link stays for the other downloads of its media until the file storage expires it, an attached one goes after its check
    is_shared: bool

    # an attached file's verdict is kept under its telegram id too, a link's media has none
    file_unique_id: FileUniqueId | None

    label: MediaLabel


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkResult:
    label: MediaLabel

    # a link that couldn't be downloaded fails as a download
    outcome: WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure | Failure

    # a check that ran has a verdict, the others couldn't check the media
    def is_verdict(self) -> bool:
        return isinstance(self.outcome, WatermarkCheck)


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkCheckRequest:
    # the command, which the reply goes under
    source: SourceMessage

    # each media in its order: a file to check, or its outcome known before the check, like a link that couldn't be downloaded or a verdict from before
    media: list[WatermarkTarget | WatermarkResult]

    @classmethod
    def from_download(cls, result: DownloadResult) -> Self:
        names_links: bool = result.request.names_links()
        targets: list[WatermarkTarget] = []

        # the media of a link follow each other
        for link, items in groupby(result.get_stored_media(), key=lambda media: media.link):
            media: list[StoredMedia] = list(items)

            targets.extend(
                WatermarkTarget(
                    storage_key=item.storage_key,
                    mime_type=item.info.mime_type,
                    size=item.info.size,
                    is_shared=True,
                    file_unique_id=None,
                    label=MediaLabel(
                        link=link if names_links else None,
                        position=position if len(media) > 1 else None,
                    ),
                )
                for position, item in enumerate(media, start=1)
            )

        failures: list[WatermarkResult] = [
            WatermarkResult(
                label=MediaLabel(link=failure.link if names_links else None, position=None),
                outcome=failure,
            )
            for failure in result.failures
        ]

        return cls(
            source=result.request.source,
            media=[*targets, *failures]
            if targets or failures
            else [WatermarkResult(label=MediaLabel.empty(), outcome=WatermarkFailure.NOT_FOUND)],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkReply:
    source: SourceMessage

    results: list[WatermarkResult]

    @classmethod
    def from_bug(cls, source: SourceMessage) -> Self:
        return cls(
            source=source,
            results=[WatermarkResult(label=MediaLabel.empty(), outcome=WatermarkFailure.BUG)],
        )
