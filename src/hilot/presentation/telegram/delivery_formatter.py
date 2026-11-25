from collections import Counter
from typing import ClassVar, override

from hilot.domain.interfaces.adapters.delivery_formatter import DeliveryFormatter
from hilot.domain.interfaces.adapters.messenger import MessageLinkReader
from hilot.domain.value_objects.download import DeliveredPost
from hilot.domain.value_objects.media import MediaKind, PostDetails
from hilot.domain.value_objects.text import RichText, TextPart

from .units import format_duration, format_size


class ChatDeliveryFormatter(DeliveryFormatter):
    _LABEL_LENGTH: ClassVar[int] = 64

    def __init__(self, *, message_link_reader: MessageLinkReader) -> None:
        self._message_link_reader: MessageLinkReader = message_link_reader

    # the name of the post leads to the message with its media
    @override
    def format_delivered_post(self, post: DeliveredPost) -> RichText:
        url: str = self._message_link_reader.get_message_link(
            chat_id=post.chat_id, message_id=post.message_id
        )
        summary: str = " · ".join(
            [self._format_media(post), format_size(sum(info.size for info in post.media))]
        )
        label: str | None = self._find_label(post.post)

        if label is None:
            return RichText((TextPart(text=summary, url=url),))

        return RichText((TextPart(text=label, url=url),)) + RichText.plain(f" · {summary}")

    @staticmethod
    def _format_media(post: DeliveredPost) -> str:
        if len(post.media) == 1:
            kind: MediaKind = post.media[0].kind
            duration: float | None = post.media[0].duration

            return kind if duration is None else f"{kind} {format_duration(duration)}"

        counts: Counter[MediaKind] = Counter(info.kind for info in post.media)

        return ", ".join(
            f"{counts[kind]} {kind}{'s' if counts[kind] > 1 else ''}"
            for kind in MediaKind
            if counts[kind]
        )

    # a post without a title is named by the start of its text, or else by its author
    @classmethod
    def _find_label(cls, post: PostDetails) -> str | None:
        if post.title is not None:
            return post.title

        if post.description is not None:
            line: str = post.description.strip().split("\n", 1)[0]

            return line if len(line) <= cls._LABEL_LENGTH else f"{line[: cls._LABEL_LENGTH - 1]}…"

        return post.author
