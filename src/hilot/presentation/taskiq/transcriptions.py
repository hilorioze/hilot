from typing import Any

from adaptix import Retort
from dishka.integrations.taskiq import FromDishka, inject

from hilot.application.transcriptions.reply import ReplyTranscription, ReplyTranscriptionDTO
from hilot.application.transcriptions.report_failure import (
    ReportTranscriptionFailure,
    ReportTranscriptionFailureDTO,
)
from hilot.application.transcriptions.transcribe import TranscribeSpeech, TranscribeSpeechDTO
from hilot.domain.value_objects.transcription import TranscriptionReply, TranscriptionRequest


@inject(patch_module=True)
async def transcribe_speech(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[TranscribeSpeech],
    failure_reporter: FromDishka[ReportTranscriptionFailure],
) -> None:
    request: TranscriptionRequest = retort.load(payload, TranscriptionRequest)

    try:
        await interactor(TranscribeSpeechDTO(request=request))
    # a bug of hilot or a failure of groq still gets the message a reply, and the task still fails for the alert
    except Exception:
        await failure_reporter(ReportTranscriptionFailureDTO(request=request))

        raise


@inject(patch_module=True)
async def reply_transcription(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[ReplyTranscription],
) -> None:
    await interactor(ReplyTranscriptionDTO(reply=retort.load(payload, TranscriptionReply)))
