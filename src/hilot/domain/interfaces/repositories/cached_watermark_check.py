from typing import Protocol

from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.value_objects.media import ContentHash


class CachedWatermarkCheckRepository(Protocol):
    async def get(self, content_hash: ContentHash) -> CachedWatermarkCheck | None: ...

    async def save(self, cached_watermark_check: CachedWatermarkCheck) -> None: ...
