from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from dishka import Provider, Scope, from_context, provide

from hilot.domain.interfaces.adapters.watermark_detector import (
    DetectableMediaMatcher,
    WatermarkDetector,
)
from hilot.domain.interfaces.repositories.detection_account import DetectionAccountRepository
from hilot.infrastructure.database.sql.repositories.detection_account import (
    SQLDetectionAccountRepository,
)
from hilot.infrastructure.synthid.attestor import SynthIDAttestor
from hilot.infrastructure.synthid.client import SynthIDClient
from hilot.infrastructure.synthid.detector import SynthIDWatermarkDetector
from hilot.infrastructure.synthid.matcher import SynthIDMediaMatcher
from hilot.main.config.worker import DetectorConfig


class DetectableMediaMatcherProvider(Provider):
    media_matcher = provide(SynthIDMediaMatcher, provides=DetectableMediaMatcher, scope=Scope.APP)


class WatermarkDetectorProvider(Provider):
    scope = Scope.APP

    detector_config = from_context(provides=DetectorConfig)

    @provide
    async def get_session(self) -> AsyncGenerator[ClientSession]:
        async with ClientSession() as session:
            yield session

    client = provide(SynthIDClient)

    @provide
    async def get_attestor(
        self, *, session: ClientSession, config: DetectorConfig
    ) -> AsyncGenerator[SynthIDAttestor]:
        async with SynthIDAttestor.open(session=session, cdp_url=config.browser_url) as attestor:
            yield attestor

    detector = provide(SynthIDWatermarkDetector, provides=WatermarkDetector)


class DetectionAccountProvider(Provider):
    account_repository = provide(
        SQLDetectionAccountRepository, provides=DetectionAccountRepository, scope=Scope.REQUEST
    )
