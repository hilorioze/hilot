from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from .media import FileUniqueId, StorageKey
from .message import SourceMessage


class TranscriptionTrigger(StrEnum):
    # a voice or a video note in a private chat, transcribed by itself
    MEDIA = "media"

    # `.stt` of the owner or of the other side of a private chat
    COMMAND = "command"


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
    trigger: TranscriptionTrigger

    file_unique_id: FileUniqueId
    storage_key: StorageKey


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriptionReply:
    source: SourceMessage
    trigger: TranscriptionTrigger

    # the transcript is kept under the file, so the same file sent again needs no transcription
    file_unique_id: FileUniqueId

    outcome: Transcript | TranscriptionQuotaExceeded | TranscriptionFailure

    # a video note is often filmed without a word, so a media transcribed by itself says nothing then
    def is_silent(self) -> bool:
        return (
            self.trigger == TranscriptionTrigger.MEDIA
            and self.outcome == TranscriptionFailure.NO_SPEECH
        )
