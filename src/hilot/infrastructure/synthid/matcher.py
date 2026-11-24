from typing import ClassVar, override

from hilot.domain.interfaces.adapters.watermark_detector import DetectableMediaMatcher

from .media_types import MEDIA_KINDS


class SynthIdMediaMatcher(DetectableMediaMatcher):
    # the page refuses bigger files of every kind
    _SIZE_LIMIT: ClassVar[int] = 100 * 1024 * 1024

    @override
    def matches(self, mime_type: str) -> bool:
        return mime_type in MEDIA_KINDS

    @override
    def get_size_limit(self) -> int:
        return self._SIZE_LIMIT
