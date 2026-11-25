from pathlib import Path
from typing import Protocol


class SpeechRecognizer(Protocol):
    async def recognize(self, path: Path) -> str: ...
