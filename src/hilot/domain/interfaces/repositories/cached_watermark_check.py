from datetime import datetime
from typing import Protocol

from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.value_objects.media import ContentHash


class CachedWatermarkCheckRepository(Protocol):
    async def get(self, content_hash: ContentHash) -> CachedWatermarkCheck | None: ...

    async def save(self, cached_watermark_check: CachedWatermarkCheck) -> None: ...

    # the telegram ids of the files go with the checks of their content
    async def delete_expired(self, now: datetime) -> None: ...
