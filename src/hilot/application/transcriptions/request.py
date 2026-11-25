from dataclasses import dataclass
from pathlib import Path

from hilot.domain.entities.cached_transcript import CachedTranscript
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    MessageMediaReader,
    ProgressIndicator,
)
from hilot.domain.interfaces.adapters.transcription_formatter import TranscriptionFormatter
from hilot.domain.interfaces.adapters.transcription_scheduler import (
    TranscriptionReplyScheduler,
    TranscriptionScheduler,
)
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.cached_transcript import CachedTranscriptRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.media import AttachedMedia, StorageKey
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    MediaLocation,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText
from hilot.domain.value_objects.transcription import (
    TranscriptionFailure,
    TranscriptionReply,
    TranscriptionRequest,
    TranscriptionTrigger,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestTranscriptionDTO:
    source: SourceMessage
    trigger: TranscriptionTrigger

    media_location: MediaLocation


class RequestTranscription:
    def __init__(
        self,
        *,
        media_reader: MessageMediaReader,
        command_answerer: CommandAnswerer,
        progress_indicator: ProgressIndicator,
        transcription_formatter: TranscriptionFormatter,
        workspace: Workspace,
        file_storage: FileStorage,
        transcription_scheduler: TranscriptionScheduler,
        reply_scheduler: TranscriptionReplyScheduler,
        cached_transcript_repository: CachedTranscriptRepository,
        uow: UnitOfWork,
    ) -> None:
        self._media_reader: MessageMediaReader = media_reader
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._transcription_formatter: TranscriptionFormatter = transcription_formatter
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._transcription_scheduler: TranscriptionScheduler = transcription_scheduler
        self._reply_scheduler: TranscriptionReplyScheduler = reply_scheduler
        self._cached_transcript_repository: CachedTranscriptRepository = (
            cached_transcript_repository
        )
        self._uow: UnitOfWork = uow

    async def __call__(self, data: RequestTranscriptionDTO) -> None:
        media: AttachedMedia | None = await self._media_reader.read_media(data.media_location)

        if media is None or not media.may_hold_speech():
            await self._command_answerer.answer_command(
                source=data.source,
                answer=CommandAnswer(
                    entries=[
                        AnswerEntry(
                            kind=AnswerKind.ERROR,
                            text=RichText.plain(
                                self._transcription_formatter.format_failure(
                                    TranscriptionFailure.NO_MEDIA
                                )
                            ),
                        )
                    ]
                ),
            )

            return

        async with self._uow:
            cached_transcript: (
                CachedTranscript | None
            ) = await self._cached_transcript_repository.get(media.file_unique_id)

        # a file sent or forwarded again keeps its telegram id, so its transcript needs no download
        if cached_transcript is not None:
            await self._reply_scheduler.schedule_transcription_reply(
                TranscriptionReply(
                    source=data.source,
                    trigger=data.trigger,
                    file_unique_id=media.file_unique_id,
                    outcome=cached_transcript.transcript,
                )
            )

            return

        # a voice is transcribed by itself only in private chats, so it shows progress wherever a command does
        if data.source.allows_reactions():
            await self._progress_indicator.show_progress(data.source)

        async with self._workspace.create() as directory:
            path: Path = await self._media_reader.download_media(media=media, directory=directory)
            storage_key: StorageKey = await self._file_storage.upload(path)

        await self._transcription_scheduler.schedule_transcription(
            TranscriptionRequest(
                source=data.source,
                trigger=data.trigger,
                file_unique_id=media.file_unique_id,
                storage_key=storage_key,
            )
        )
