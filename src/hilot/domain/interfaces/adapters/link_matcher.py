from typing import Protocol


class LinkMatcher(Protocol):
    def matches(self, url: str) -> bool: ...
