from typing import Protocol

from hilot.domain.value_objects.media import PostDetails
from hilot.domain.value_objects.text import RichText


class CaptionFormatter(Protocol):
    # without a limit the caption comes whole
    def format_caption(self, *, post: PostDetails, limit: int | None) -> RichText | None: ...
