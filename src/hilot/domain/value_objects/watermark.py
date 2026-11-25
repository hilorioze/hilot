from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from .media import StorageKey
from .message import SourceMessage


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
    UNSUPPORTED = "unsupported"
    TOO_BIG = "too_big"
    BUG = "bug"


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkQuotaExceeded:
    retry_after: timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkCheckRequest:
    # the command, which the reply goes under
    source: SourceMessage

    storage_key: StorageKey
    mime_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WatermarkReply:
    source: SourceMessage

    outcome: WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure

    # a check that ran has a verdict, the others couldn't check the media
    def is_verdict(self) -> bool:
        return isinstance(self.outcome, WatermarkCheck)
