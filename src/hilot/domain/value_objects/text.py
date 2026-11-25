from dataclasses import dataclass
from typing import Self


# a piece of a text, which opens its url on a tap when it has one
@dataclass(frozen=True, slots=True, kw_only=True)
class TextPart:
    text: str
    url: str | None


@dataclass(frozen=True, slots=True)
class RichText:
    parts: tuple[TextPart, ...]

    @classmethod
    def plain(cls, text: str) -> Self:
        return cls((TextPart(text=text, url=None),))

    @classmethod
    def join(cls, *, separator: str, texts: list[RichText]) -> Self:
        return cls(
            tuple(
                part
                for index, text in enumerate(texts)
                for part in (*(cls.plain(separator).parts if index else ()), *text.parts)
            )
        )

    def __add__(self, other: RichText) -> RichText:
        return RichText((*self.parts, *other.parts))
