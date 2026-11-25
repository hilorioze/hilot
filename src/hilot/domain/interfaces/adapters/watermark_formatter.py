from typing import Protocol

from hilot.domain.value_objects.watermark import (
    WatermarkCheck,
    WatermarkFailure,
    WatermarkQuotaExceeded,
    WatermarkResult,
)


class WatermarkFormatter(Protocol):
    def format_outcome(
        self, outcome: WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure
    ) -> str: ...

    # a download failure names the detector's limit
    def format_result(self, *, result: WatermarkResult, size_limit: int) -> str: ...
