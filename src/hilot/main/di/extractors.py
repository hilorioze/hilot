from dishka import Provider, Scope, from_context, provide

from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.media_extractor import MediaExtractor
from hilot.infrastructure.extractors.composite import AnyLinkMatcher, FallbackMediaExtractor
from hilot.infrastructure.extractors.gallery_dl import (
    GalleryDlLinkMatcher,
    GalleryDlMediaExtractor,
)
from hilot.infrastructure.extractors.yt_dlp import YtDlpLinkMatcher, YtDlpMediaExtractor
from hilot.main.config.worker import DownloaderConfig


class LinkMatcherProvider(Provider):
    @provide(scope=Scope.APP)
    def get_link_matcher(self) -> LinkMatcher:
        return AnyLinkMatcher(matchers=[YtDlpLinkMatcher(), GalleryDlLinkMatcher()])


class MediaExtractorProvider(Provider):
    config = from_context(provides=DownloaderConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def get_media_extractor(self, config: DownloaderConfig) -> MediaExtractor:
        proxy: str | None = config.proxy.get_secret_value() if config.proxy is not None else None

        return FallbackMediaExtractor(
            # yt-dlp takes the videos, gallery-dl the photo posts, and yt-dlp again the audio
            extractors=[
                YtDlpMediaExtractor(proxy=proxy, video_required=True),
                GalleryDlMediaExtractor(proxy=proxy),
                YtDlpMediaExtractor(proxy=proxy, video_required=False),
            ]
        )
