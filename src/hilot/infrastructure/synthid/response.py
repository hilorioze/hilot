import json
from datetime import timedelta
from typing import Any

from hilot.domain.value_objects.watermark import (
    UndeterminedReason,
    WatermarkCheck,
    WatermarkConfidence,
    WatermarkSegment,
    WatermarkVerdict,
)

from .errors import DetectionRefusedError, QuotaExceededError

# the fields are those of the page's protobuf messages, read from its javascript
_VERDICTS: dict[int, WatermarkVerdict] = {
    1: WatermarkVerdict.UNDETERMINED,
    2: WatermarkVerdict.NOT_DETECTED,
    3: WatermarkVerdict.DETECTED,
}

# the page reads each code for its own media kind, but no code is used by two kinds
_REASONS: dict[int | None, UndeterminedReason] = {
    1: UndeterminedReason.EMPTY,
    2: UndeterminedReason.LOW_RESOLUTION,
    3: UndeterminedReason.NOT_ENOUGH_DETAIL,
    4: UndeterminedReason.LOW_FPS,
    5: UndeterminedReason.LOW_QUALITY,
    6: UndeterminedReason.POSSIBLE_TAMPERING,
    7: UndeterminedReason.TOO_LONG,
}

_CONFIDENCES: dict[int, WatermarkConfidence] = {
    4: WatermarkConfidence.MEDIUM,
    5: WatermarkConfidence.HIGH,
    6: WatermarkConfidence.VERY_HIGH,
}

# google's own models have a code, the other partners send their name
_GOOGLE_PROVIDER: int = 1
_NAMED_PROVIDER: int = 2


def parse_response(text: str) -> WatermarkCheck:
    response: list[Any] = _read_response(text)
    quota: list[Any] | None = _get_field(response, 7)

    # a quota error comes in place of the result, with the duration until the quota resets
    if quota is not None:
        retry_after: list[int] = _get_field(quota[0], 4)

        raise QuotaExceededError(
            timedelta(
                seconds=_get_field(retry_after, 1) or 0,
                microseconds=(_get_field(retry_after, 2) or 0) / 1000,
            )
        )

    return _parse_result(_get_field(response, 5)[0])


def _read_response(text: str) -> list[Any]:
    # a streamed batchexecute response is a guard line, then chunks of a length line and a json line
    for line in text.splitlines():
        if not line.startswith("[["):
            continue

        for entry in json.loads(line):
            if entry[:2] != ["wrb.fr", "TZRKo"]:
                continue

            if entry[2] is None:
                raise DetectionRefusedError(entry[5])

            return json.loads(entry[2])

    raise DetectionRefusedError(None)


def _parse_result(result: list[Any]) -> WatermarkCheck:
    verdict: WatermarkVerdict = _VERDICTS[_get_field(result, 1)]
    video: list[Any] | None = _get_field(result, 8)

    return WatermarkCheck(
        verdict=verdict,
        reason=_read_reason(verdict=verdict, code=_get_field(result, 10)),
        confidence=_CONFIDENCES.get(_get_field(result, 13)),
        provider=_read_provider(code=_get_field(result, 11), name=_get_field(result, 12)),
        # a video has the segments of its picture and of its sound, an audio only its own
        video_segments=_parse_segments(_get_field(video, 1) if video else None),
        audio_segments=_parse_segments(_get_field(video, 2) if video else _get_field(result, 2)),
    )


def _parse_segments(segments: list[list[int]] | None) -> list[WatermarkSegment]:
    return [
        WatermarkSegment(
            start=_get_field(segment, 1) or 0,
            end=_get_field(segment, 2) or 0,
            verdict=_VERDICTS[_get_field(segment, 3)],
        )
        for segment in segments or []
    ]


def _read_reason(*, verdict: WatermarkVerdict, code: int | None) -> UndeterminedReason | None:
    if verdict != WatermarkVerdict.UNDETERMINED:
        return None

    return _REASONS.get(code, UndeterminedReason.UNKNOWN)


def _read_provider(*, code: int | None, name: str | None) -> str | None:
    if code == _GOOGLE_PROVIDER:
        return "google"

    if code == _NAMED_PROVIDER:
        return name

    return None


# a field of a json protobuf message sits at its number minus one, and the trailing empty ones are cut off
def _get_field(message: list[Any], number: int) -> Any:  # noqa: ANN401
    return message[number - 1] if len(message) >= number else None
