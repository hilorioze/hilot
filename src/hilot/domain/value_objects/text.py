from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class TextStyle(StrEnum):
    BOLD = "bold"
    # a quote that shows its first lines and opens the rest on a tap
    EXPANDABLE_QUOTE = "expandable_quote"


# a piece of a text, which opens its url on a tap when it has one
@dataclass(frozen=True, slots=True, kw_only=True)
class TextPart:
    text: str
    url: str | None
    styles: frozenset[TextStyle] = frozenset()


@dataclass(frozen=True, slots=True)
class RichText:
    parts: tuple[TextPart, ...]

    @classmethod
    def plain(cls, text: str) -> Self:
        return cls((TextPart(text=text, url=None),))

    @classmethod
    def styled(cls, text: str, *, style: TextStyle) -> Self:
        return cls((TextPart(text=text, url=None, styles=frozenset({style})),))

    @classmethod
    def join(cls, *, separator: str, texts: list[RichText]) -> Self:
        return cls(
            tuple(
                part
                for index, text in enumerate(texts)
                for part in (*(cls.plain(separator).parts if index else ()), *text.parts)
            )
        )

    def get_text(self) -> str:
        return "".join(part.text for part in self.parts)

    def __add__(self, other: RichText) -> RichText:
        return RichText((*self.parts, *other.parts))
