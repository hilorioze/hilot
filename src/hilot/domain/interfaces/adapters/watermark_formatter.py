from typing import Protocol

from hilot.domain.value_objects.watermark import (
    WatermarkCheck,
    WatermarkFailure,
    WatermarkQuotaExceeded,
)


class WatermarkFormatter(Protocol):
    def format_outcome(
        self, outcome: WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure
    ) -> str: ...
