from typing import override

from hilot.domain.interfaces.adapters.text_measurer import TextMeasurer


class TelegramTextMeasurer(TextMeasurer):
    # telegram counts the limits in utf-16 code units
    @override
    def measure(self, text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
