from typing import Protocol


# the length the limits of the messenger count
class TextMeasurer(Protocol):
    def measure(self, text: str) -> int: ...
