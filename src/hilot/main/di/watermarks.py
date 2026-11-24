from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from dishka import Provider, Scope, from_context, provide
from yarl import URL

from hilot.domain.interfaces.adapters.watermark_detector import (
    DetectableMediaMatcher,
    WatermarkDetector,
)
from hilot.infrastructure.synthid.accounts import IDToken, SynthIDAccountPool
from hilot.infrastructure.synthid.attestor import SynthIDAttestor
from hilot.infrastructure.synthid.client import SynthIDClient
from hilot.infrastructure.synthid.detector import SynthIDWatermarkDetector
from hilot.infrastructure.synthid.matcher import SynthIDMediaMatcher
from hilot.main.config.synthid import SynthIDConfig
from hilot.main.config.worker import DetectorConfig


class DetectableMediaMatcherProvider(Provider):
    media_matcher = provide(SynthIDMediaMatcher, provides=DetectableMediaMatcher, scope=Scope.APP)


class WatermarkDetectorProvider(Provider):
    scope = Scope.APP

    detector_config = from_context(provides=DetectorConfig)
    synthid_config = from_context(provides=SynthIDConfig)

    @provide
    async def get_session(self) -> AsyncGenerator[ClientSession]:
        async with ClientSession() as session:
            yield session

    client = provide(SynthIDClient)

    @provide
    def get_account_pool(self, config: SynthIDConfig) -> SynthIDAccountPool:
        return SynthIDAccountPool(
            [refresh_token.get_secret_value() for refresh_token in config.refresh_tokens]
        )

    @provide
    async def get_attestor(
        self,
        *,
        session: ClientSession,
        client: SynthIDClient,
        detector_config: DetectorConfig,
        synthid_config: SynthIDConfig,
    ) -> AsyncGenerator[SynthIDAttestor]:
        # the page attests for any account, so it stays signed in to the first one
        refresh_token: str = synthid_config.refresh_tokens[0].get_secret_value()
        id_token: IDToken = await client.refresh_id_token(refresh_token)

        async with SynthIDAttestor.open(
            session=session,
            cdp_url=detector_config.browser_url,
            proxy=URL(detector_config.proxy.get_secret_value())
            if detector_config.proxy is not None
            else None,
            uid=id_token.uid,
            refresh_token=refresh_token,
        ) as attestor:
            yield attestor

    detector = provide(SynthIDWatermarkDetector, provides=WatermarkDetector)
