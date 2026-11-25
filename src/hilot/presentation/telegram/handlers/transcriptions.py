from dishka import FromDishka
from pyrogram import Client, filters
from pyrogram.types import Message

from hilot.application.transcriptions.request import (
    RequestTranscription,
    RequestTranscriptionDTO,
)
from hilot.domain.value_objects.message import AccountId
from hilot.domain.value_objects.transcription import TranscriptionTrigger
from hilot.presentation.telegram.filters import CALLER, BotChatFilter
from hilot.presentation.telegram.parsing import parse_media_location, parse_source
from hilot.presentation.telegram.router import Router

router: Router = Router()


# the command transcribes the media it replies to, or the one it's the caption of
@router.on_message(CALLER & filters.command(["stt"], prefixes="."))
async def request_transcription(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestTranscription],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestTranscriptionDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=TranscriptionTrigger.COMMAND,
            media_location=parse_media_location(message),
        )
    )


# a voice or a video note in a private chat is transcribed by itself, the owner's and the other side's alike
@router.on_message((filters.voice | filters.video_note) & filters.private & ~BotChatFilter())
async def transcribe_voice(
    _: Client,
    message: Message,
    interactor: FromDishka[RequestTranscription],
    account_id: FromDishka[AccountId],
) -> None:
    await interactor(
        RequestTranscriptionDTO(
            source=parse_source(message=message, account_id=account_id),
            trigger=TranscriptionTrigger.MEDIA,
            media_location=parse_media_location(message),
        )
    )
