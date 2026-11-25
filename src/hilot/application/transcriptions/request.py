from dataclasses import dataclass
from pathlib import Path

from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    MessageMediaReader,
    ProgressIndicator,
)
from hilot.domain.interfaces.adapters.transcription_formatter import TranscriptionFormatter
from hilot.domain.interfaces.adapters.transcription_scheduler import TranscriptionScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.value_objects.media import AttachedMedia, StorageKey
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    MediaLocation,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText
from hilot.domain.value_objects.transcription import TranscriptionFailure, TranscriptionRequest


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestTranscriptionDTO:
    source: SourceMessage

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
    ) -> None:
        self._media_reader: MessageMediaReader = media_reader
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._transcription_formatter: TranscriptionFormatter = transcription_formatter
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._transcription_scheduler: TranscriptionScheduler = transcription_scheduler

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

        # a voice is transcribed by itself only in private chats, so it shows progress wherever a command does
        if data.source.allows_reactions():
            await self._progress_indicator.show_progress(data.source)

        async with self._workspace.create() as directory:
            path: Path = await self._media_reader.download_media(media=media, directory=directory)
            storage_key: StorageKey = await self._file_storage.upload(path)

        await self._transcription_scheduler.schedule_transcription(
            TranscriptionRequest(source=data.source, storage_key=storage_key)
        )
