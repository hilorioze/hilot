from pathlib import Path
from typing import Protocol


# the audio of a media, as small as the recognizer still hears the speech in it
class SpeechExtractor(Protocol):
    async def extract_speech(self, *, path: Path, directory: Path) -> Path: ...
