from pathlib import Path
from typing import Protocol

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.value_objects.media import MediaKind
from hilot.domain.value_objects.watermark import WatermarkCheck


class DetectableMediaMatcher(Protocol):
    def matches(self, mime_type: str) -> bool: ...

    def get_size_limit(self) -> int: ...

    # the media kind whose quota a check of the type takes
    def get_kind(self, mime_type: str) -> MediaKind: ...


class WatermarkDetector(Protocol):
    async def detect(
        self, *, account: DetectionAccount, path: Path, mime_type: str
    ) -> WatermarkCheck: ...
