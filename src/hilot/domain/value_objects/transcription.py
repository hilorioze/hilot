from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from .media import StorageKey
from .message import SourceMessage


class TranscriptionFailure(StrEnum):
    NO_MEDIA = "no_media"
    NO_SPEECH = "no_speech"
    TOO_LONG = "too_long"
    BUG = "bug"


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptionQuotaExceeded:
    retry_after: timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcript:
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptionRequest:
    # the voice message or the command, which the transcript goes under
    source: SourceMessage

    storage_key: StorageKey


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptionReply:
    source: SourceMessage

    outcome: Transcript | TranscriptionQuotaExceeded | TranscriptionFailure
