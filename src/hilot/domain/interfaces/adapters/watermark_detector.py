from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.watermark import WatermarkCheck


class DetectableMediaMatcher(Protocol):
    def matches(self, mime_type: str) -> bool: ...

    def get_size_limit(self) -> int: ...


class WatermarkDetector(Protocol):
    async def detect(self, *, path: Path, mime_type: str) -> WatermarkCheck: ...
