from hilot.domain.interfaces.adapters.watermark_detector import DetectableMediaMatcher
from hilot.domain.value_objects.watermark import WatermarkFailure


# the detector takes only some types of media, up to its size limit
def find_media_failure(
    *, media_matcher: DetectableMediaMatcher, mime_type: str, size: int
) -> WatermarkFailure | None:
    if not media_matcher.matches(mime_type):
        return WatermarkFailure.UNSUPPORTED

    if size > media_matcher.get_size_limit():
        return WatermarkFailure.TOO_BIG

    return None
