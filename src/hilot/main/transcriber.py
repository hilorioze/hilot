import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.transcriptions.report_failure import ReportTranscriptionFailure
from hilot.application.transcriptions.transcribe import TranscribeSpeech
from hilot.infrastructure.queue.routes import TRANSCRIPTION_ROUTE, Route
from hilot.presentation.taskiq.transcriptions import transcribe_speech

from .config.groq import GroqConfig
from .config.loader import load_config
from .config.nats import NATSConfig
from .config.s3 import S3Config
from .config.schemas import TranscriberSchema
from .di.media import WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider
from .di.transcriptions import SpeechRecognizerProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(TranscribeSpeech, ReportTranscriptionFailure)


async def run() -> None:
    schema: TranscriberSchema = load_config(schema=TranscriberSchema, secrets_scope="transcriber")

    container: AsyncContainer = make_async_container(
        S3Provider(),
        QueueProvider(),
        WorkspaceProvider(),
        SpeechRecognizerProvider(),
        _InteractorProvider(),
        context={
            S3Config: schema.s3,
            NATSConfig: schema.nats,
            GroqConfig: schema.groq,
            Route: TRANSCRIPTION_ROUTE,
        },
    )

    await run_worker(
        container=container,
        config=schema.transcriber,
        tasks={TRANSCRIPTION_ROUTE: transcribe_speech},
    )

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
