import subprocess
from pathlib import Path
from typing import ClassVar, override

from hilot.domain.errors.extraction import MediaUnavailableError
from hilot.domain.interfaces.adapters.media_transcoder import MediaTranscoder
from hilot.domain.value_objects.media import MediaKind

from .process import run_process


class FfmpegMediaTranscoder(MediaTranscoder):
    _SUFFIXES: ClassVar[dict[MediaKind, str]] = {
        MediaKind.PHOTO: ".jpg",
        MediaKind.VIDEO: ".mp4",
        MediaKind.AUDIO: ".m4a",
    }

    _OUTPUT_ARGS: ClassVar[dict[MediaKind, list[str]]] = {
        MediaKind.PHOTO: ["-frames:v", "1", "-qscale:v", "2"],
        MediaKind.VIDEO: [
            "-map",
            # `V` skips the covers
            "0:V:0",
            "-map",
            "0:a:0?",
            "-codec:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            # h264 in yuv420p takes only even dimensions
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-codec:a",
            "aac",
            "-movflags",
            "+faststart",
        ],
        MediaKind.AUDIO: ["-map", "0:a:0", "-codec:a", "aac", "-movflags", "+faststart"],
    }

    @override
    async def transcode(
        self, *, path: Path, kind: MediaKind, directory: Path, size_limit: int
    ) -> Path:
        output: Path = directory / f"{path.stem}{self._SUFFIXES[kind]}"

        try:
            await run_process(
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                path,
                *self._OUTPUT_ARGS[kind],
                # `-fs` stops writing a bit past the limit, so a too big output still shows as such
                "-fs",
                str(size_limit),
                output,
            )
        except subprocess.CalledProcessError as error:
            raise MediaUnavailableError from error

        return output
