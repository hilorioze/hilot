from collections.abc import AsyncGenerator

from dishka import Provider, Scope, from_context, provide
from groq import AsyncGroq

from hilot.domain.interfaces.adapters.speech_extractor import SpeechExtractor
from hilot.domain.interfaces.adapters.speech_recognizer import SpeechRecognizer
from hilot.domain.interfaces.repositories.cached_transcript import (
    CachedTranscriptExpiryRepository,
    CachedTranscriptRepository,
)
from hilot.infrastructure.database.sql.repositories.cached_transcript import (
    SQLCachedTranscriptExpiryRepository,
    SQLCachedTranscriptRepository,
)
from hilot.infrastructure.ffmpeg.speech_extractor import FfmpegSpeechExtractor
from hilot.infrastructure.groq.recognizer import GroqSpeechRecognizer
from hilot.main.config.groq import GroqConfig


class SpeechRecognizerProvider(Provider):
    scope = Scope.APP

    config = from_context(provides=GroqConfig)

    @provide
    async def get_client(self, config: GroqConfig) -> AsyncGenerator[AsyncGroq]:
        async with AsyncGroq(api_key=config.api_key.get_secret_value()) as client:
            yield client

    speech_recognizer = provide(GroqSpeechRecognizer, provides=SpeechRecognizer)
    speech_extractor = provide(FfmpegSpeechExtractor, provides=SpeechExtractor)


class CachedTranscriptProvider(Provider):
    cached_transcript_repository = provide(
        SQLCachedTranscriptRepository, provides=CachedTranscriptRepository, scope=Scope.REQUEST
    )


class CachedTranscriptExpiryProvider(Provider):
    cached_transcript_expiry_repository = provide(
        SQLCachedTranscriptExpiryRepository,
        provides=CachedTranscriptExpiryRepository,
        scope=Scope.REQUEST,
    )
