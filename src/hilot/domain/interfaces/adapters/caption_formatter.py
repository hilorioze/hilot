from typing import Protocol

from hilot.domain.value_objects.media import PostDetails


class CaptionFormatter(Protocol):
    def format_caption(self, *, post: PostDetails, limit: int) -> str | None: ...
