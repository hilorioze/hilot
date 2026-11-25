from typing import ClassVar, override

from hilot.domain.interfaces.adapters.caption_formatter import CaptionFormatter
from hilot.domain.value_objects.media import PostDetails


class ChatCaptionFormatter(CaptionFormatter):
    _ELLIPSIS: ClassVar[str] = "…"

    @override
    def format_caption(self, *, post: PostDetails, limit: int) -> str | None:
        heading: str = "\n".join(
            line
            for line in (
                None if self._repeats_description(post) else post.title,
                f"by {post.author}" if post.author else None,
            )
            if line
        )
        text: str = "\n\n".join(part for part in (heading, post.description) if part)

        return self._truncate(text=text, limit=limit) if text else None

    # most sites title a post after the start of its text
    @classmethod
    def _repeats_description(cls, post: PostDetails) -> bool:
        if post.title is None or post.description is None:
            return False

        return post.description.startswith(
            post.title.removesuffix(cls._ELLIPSIS).removesuffix("...")
        )

    # telegram counts the limit in utf-16 code units
    @classmethod
    def _truncate(cls, *, text: str, limit: int) -> str:
        encoded: bytes = text.encode("utf-16-le")

        if len(encoded) // 2 <= limit:
            return text

        # a cut through a surrogate pair drops its half
        kept: str = encoded[: (limit - len(cls._ELLIPSIS)) * 2].decode(
            "utf-16-le", errors="ignore"
        )

        return f"{kept.rstrip()}{cls._ELLIPSIS}"
