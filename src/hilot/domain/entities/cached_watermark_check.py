from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from hilot.domain.value_objects.media import ContentHash
from hilot.domain.value_objects.watermark import WatermarkCheck, WatermarkVerdict


# the verdict on the content of a file, which the same content gets again without spending a quota
@dataclass(frozen=True, slots=True, kw_only=True)
class CachedWatermarkCheck:
    # a found watermark stays in the file, while the detector may learn the generator of a file it found nothing in
    _NOT_DETECTED_LIFETIME: ClassVar[timedelta] = timedelta(days=1)

    content_hash: ContentHash

    check: WatermarkCheck = field(compare=False)
    checked_at: datetime = field(compare=False)

    # `None` for a verdict that never expires
    def get_expiry(self) -> datetime | None:
        if self.check.verdict == WatermarkVerdict.DETECTED:
            return None

        return self.checked_at + self._NOT_DETECTED_LIFETIME

    def is_fresh(self, now: datetime) -> bool:
        expiry: datetime | None = self.get_expiry()

        return expiry is None or now < expiry
