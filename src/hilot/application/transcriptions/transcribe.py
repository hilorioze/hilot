import asyncio
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

from hilot.domain.errors.transcription import (
    NoAudioError,
    SpeechTooLongError,
    TranscriptionQuotaExceededError,
)
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.speech_extractor import SpeechExtractor
from hilot.domain.interfaces.adapters.speech_recognizer import SpeechRecognizer
from hilot.domain.interfaces.adapters.transcription_scheduler import TranscriptionReplyScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.value_objects.transcription import (
    Transcript,
    TranscriptionFailure,
    TranscriptionQuotaExceeded,
    TranscriptionReply,
    TranscriptionRequest,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscribeSpeechDTO:
    request: TranscriptionRequest


class TranscribeSpeech:
    # a minute's limit frees up while the transcription waits, a longer one gets the wait in the reply
    _MAX_WAIT: ClassVar[timedelta] = timedelta(minutes=1)

    def __init__(
        self,
        *,
        speech_extractor: SpeechExtractor,
        speech_recognizer: SpeechRecognizer,
        workspace: Workspace,
        file_storage: FileStorage,
        reply_scheduler: TranscriptionReplyScheduler,
    ) -> None:
        self._speech_extractor: SpeechExtractor = speech_extractor
        self._speech_recognizer: SpeechRecognizer = speech_recognizer
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._reply_scheduler: TranscriptionReplyScheduler = reply_scheduler

    async def __call__(self, data: TranscribeSpeechDTO) -> None:
        # a failed task isn't retried, so its media goes either way
        try:
            async with self._workspace.create() as directory:
                path: Path = directory / "media"
                await self._file_storage.download(key=data.request.storage_key, path=path)

                outcome: (
                    Transcript | TranscriptionQuotaExceeded | TranscriptionFailure
                ) = await self._transcribe(path=path, directory=directory)
        finally:
            await self._file_storage.delete(data.request.storage_key)

        await self._reply_scheduler.schedule_transcription_reply(
            TranscriptionReply(
                source=data.request.source,
                trigger=data.request.trigger,
                file_unique_id=data.request.file_unique_id,
                outcome=outcome,
            )
        )

    async def _transcribe(
        self, *, path: Path, directory: Path
    ) -> Transcript | TranscriptionQuotaExceeded | TranscriptionFailure:
        try:
            speech: Path = await self._speech_extractor.extract_speech(
                path=path, directory=directory
            )
        except NoAudioError:
            return TranscriptionFailure.NO_SPEECH

        while True:
            try:
                text: str = await self._speech_recognizer.recognize(speech)
            except SpeechTooLongError:
                return TranscriptionFailure.TOO_LONG
            except TranscriptionQuotaExceededError as error:
                if error.retry_after > self._MAX_WAIT:
                    return TranscriptionQuotaExceeded(retry_after=error.retry_after)

                await asyncio.sleep(error.retry_after.total_seconds())
            else:
                break

        # whisper writes only punctuation for a record without speech
        if not any(character.isalnum() for character in text):
            return TranscriptionFailure.NO_SPEECH

        return Transcript(text=text.strip())
