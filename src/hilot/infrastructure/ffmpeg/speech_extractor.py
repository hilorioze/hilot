from pathlib import Path
from typing import override

from hilot.domain.errors.transcription import NoAudioError
from hilot.domain.interfaces.adapters.speech_extractor import SpeechExtractor

from .process import run_process


class FfmpegSpeechExtractor(SpeechExtractor):
    @override
    async def extract_speech(self, *, path: Path, directory: Path) -> Path:
        audio_streams: bytes = await run_process(
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-print_format",
            "csv",
            "--",
            path,
        )

        if not audio_streams.strip():
            raise NoAudioError

        output: Path = directory / "speech.ogg"

        await run_process(
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            path,
            "-map",
            "0:a:0",
            # whisper hears in 16 khz mono, and opus keeps the speech in a fraction of the size of the recognizer's file limit
            "-ac",
            "1",
            "-ar",
            "16000",
            "-codec:a",
            "libopus",
            "-b:a",
            "32k",
            output,
        )

        return output
