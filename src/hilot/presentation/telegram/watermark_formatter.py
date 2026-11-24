import math
from datetime import timedelta
from typing import ClassVar, override

from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.value_objects.watermark import (
    UndeterminedReason,
    WatermarkCheck,
    WatermarkConfidence,
    WatermarkFailure,
    WatermarkQuotaExceeded,
    WatermarkSegment,
    WatermarkVerdict,
)


class ChatWatermarkFormatter(WatermarkFormatter):
    _FAILURE_TEXTS: ClassVar[dict[WatermarkFailure, str]] = {
        WatermarkFailure.NO_MEDIA: "nothing to check, reply to a photo, video or audio",
        WatermarkFailure.UNSUPPORTED: "synthid can't check this type",
        WatermarkFailure.TOO_BIG: "too big for synthid",
        WatermarkFailure.BUG: "something broke on my side",
    }

    _REASON_TEXTS: ClassVar[dict[UndeterminedReason, str]] = {
        UndeterminedReason.EMPTY: "it's empty",
        UndeterminedReason.LOW_RESOLUTION: "resolution is too low",
        UndeterminedReason.NOT_ENOUGH_DETAIL: "not enough detail",
        UndeterminedReason.LOW_QUALITY: "quality is too low",
        UndeterminedReason.POSSIBLE_TAMPERING: "looks edited",
        UndeterminedReason.LOW_FPS: "frame rate is too low",
        UndeterminedReason.TOO_LONG: "it's too long",
    }

    _CONFIDENCE_TEXTS: ClassVar[dict[WatermarkConfidence, str]] = {
        WatermarkConfidence.MEDIUM: "medium confidence",
        WatermarkConfidence.HIGH: "high confidence",
        WatermarkConfidence.VERY_HIGH: "very high confidence",
    }

    @override
    def format_outcome(
        self, outcome: WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure
    ) -> str:
        if isinstance(outcome, WatermarkFailure):
            return self._FAILURE_TEXTS[outcome]

        if isinstance(outcome, WatermarkQuotaExceeded):
            return f"out of synthid checks, try again in {self._format_wait(outcome.retry_after)}"

        match outcome.verdict:
            case WatermarkVerdict.DETECTED:
                return "\n".join(self._describe_detection(outcome))
            case WatermarkVerdict.NOT_DETECTED:
                return "no synthid watermark"
            case WatermarkVerdict.UNDETERMINED:
                reason: str | None = (
                    self._REASON_TEXTS.get(outcome.reason) if outcome.reason else None
                )

                return f"synthid can't tell, {reason}" if reason else "synthid can't tell"

    def _describe_detection(self, check: WatermarkCheck) -> list[str]:
        details: list[str] = [
            detail
            for detail in (
                f"made with {check.provider}" if check.provider else None,
                self._CONFIDENCE_TEXTS[check.confidence] if check.confidence else None,
            )
            if detail is not None
        ]
        lines: list[str] = [
            f"synthid watermark found, {', '.join(details)}"
            if details
            else "synthid watermark found"
        ]

        # a video or an audio is checked in pieces, which can be watermarked apart
        for name, segments in (("video", check.video_segments), ("audio", check.audio_segments)):
            ranges: list[tuple[int, int]] = self._merge_detected(segments)

            if ranges:
                lines.append(
                    f"{name}: {', '.join(f'{self._format_time(start)}-{self._format_time(end)}' for start, end in ranges)}"
                )

        return lines

    @staticmethod
    def _merge_detected(segments: list[WatermarkSegment]) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []

        for segment in segments:
            if segment.verdict != WatermarkVerdict.DETECTED:
                continue

            # the pieces follow each other, so the adjacent watermarked ones make one range
            if ranges and ranges[-1][1] == segment.start:
                ranges[-1] = (ranges[-1][0], segment.end)
            else:
                ranges.append((segment.start, segment.end))

        return ranges

    @staticmethod
    def _format_wait(wait: timedelta) -> str:
        hours: int = math.ceil(wait.total_seconds() / 3600)

        return f"{hours} h" if hours > 1 else f"{math.ceil(wait.total_seconds() / 60)} min"

    @staticmethod
    def _format_time(seconds: int) -> str:
        return f"{seconds // 60}:{seconds % 60:02}"
