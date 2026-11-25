import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, override

from adaptix import Retort
from groq import AsyncGroq, RateLimitError
from groq.types.audio.transcription import Transcription

from hilot.domain.errors.transcription import (
    SpeechTooLongError,
    TranscriptionQuotaExceededError,
)
from hilot.domain.interfaces.adapters.speech_recognizer import SpeechRecognizer


@dataclass(frozen=True, slots=True, kw_only=True)
class _Segment:
    text: str

    # whisper's own estimate that the segment holds no speech
    no_speech_prob: float


@dataclass(frozen=True, slots=True, kw_only=True)
class _VerboseTranscription:
    segments: list[_Segment]


class GroqSpeechRecognizer(SpeechRecognizer):
    _MODEL: ClassVar[str] = "whisper-large-v3"

    # the limit of an uploaded file on the free tier
    _SIZE_LIMIT: ClassVar[int] = 25 * 1024**2

    # whisper makes up a short phrase for silence with a fair confidence in its words, but not in the speech
    _NO_SPEECH_THRESHOLD: ClassVar[float] = 0.6

    # the sdk types only the text of a transcription
    _RETORT: ClassVar[Retort] = Retort()

    def __init__(self, *, client: AsyncGroq) -> None:
        self._client: AsyncGroq = client

    @override
    async def recognize(self, path: Path) -> str:
        if (await asyncio.to_thread(path.stat)).st_size > self._SIZE_LIMIT:
            raise SpeechTooLongError

        # the client itself waits out the limits that reset within a minute
        try:
            transcription: Transcription = await self._client.audio.transcriptions.create(
                file=path, model=self._MODEL, temperature=0, response_format="verbose_json"
            )
        except RateLimitError as error:
            raise TranscriptionQuotaExceededError(
                timedelta(seconds=float(error.response.headers["retry-after"]))
            ) from error

        verbose: _VerboseTranscription = self._RETORT.load(
            transcription.model_dump(), _VerboseTranscription
        )

        return "".join(
            segment.text
            for segment in verbose.segments
            if segment.no_speech_prob <= self._NO_SPEECH_THRESHOLD
        )
