from dataclasses import replace
from typing import ClassVar, override

from hilot.domain.interfaces.adapters.caption_formatter import CaptionFormatter
from hilot.domain.interfaces.adapters.text_measurer import TextMeasurer
from hilot.domain.value_objects.media import PostDetails
from hilot.domain.value_objects.text import RichText, TextStyle


class ChatCaptionFormatter(CaptionFormatter):
    _ELLIPSIS: ClassVar[str] = "…"

    def __init__(self, *, text_measurer: TextMeasurer) -> None:
        self._text_measurer: TextMeasurer = text_measurer

    @override
    def format_caption(self, *, post: PostDetails, limit: int | None) -> RichText | None:
        heading: list[RichText] = [
            *(
                (RichText.styled(post.title, style=TextStyle.BOLD),)
                if post.title and not self._repeats_description(post)
                else ()
            ),
            *((RichText.plain(f"by {post.author}"),) if post.author else ()),
        ]
        # telegram strips the trailing whitespace of a text and drops an entity reaching into it
        description: str = (post.description or "").strip()
        sections: list[RichText] = [
            *((RichText.join(separator="\n", texts=heading),) if heading else ()),
            *(
                (RichText.styled(description, style=TextStyle.EXPANDABLE_QUOTE),)
                if description
                else ()
            ),
        ]

        if not sections:
            return None

        caption: RichText = RichText.join(separator="\n\n", texts=sections)

        return caption if limit is None else self._truncate(text=caption, limit=limit)

    # most sites title a post after the start of its text
    @classmethod
    def _repeats_description(cls, post: PostDetails) -> bool:
        if post.title is None or post.description is None:
            return False

        return post.description.startswith(
            post.title.removesuffix(cls._ELLIPSIS).removesuffix("...")
        )

    # the cut part keeps its style, so a cut description stays in its quote
    def _truncate(self, *, text: RichText, limit: int) -> RichText:
        if self._text_measurer.measure(text.get_text()) <= limit:
            return text

        room: int = limit - self._text_measurer.measure(self._ELLIPSIS)

        for index, part in enumerate(text.parts):
            length: int = self._text_measurer.measure(part.text)

            if length > room:
                # a cut through a surrogate pair drops its half
                kept: str = part.text.encode("utf-16-le")[: room * 2].decode(
                    "utf-16-le", errors="ignore"
                )

                return RichText(
                    (*text.parts[:index], replace(part, text=f"{kept.rstrip()}{self._ELLIPSIS}"))
                )

            room -= length

        return text
