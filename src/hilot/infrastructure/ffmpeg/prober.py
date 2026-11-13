import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

from adaptix import Retort

from hilot.domain.errors.extraction import MediaUnavailableError
from hilot.domain.interfaces.adapters.media_prober import MediaProber
from hilot.domain.value_objects.media import MediaInfo, MediaKind

from .process import run_process


@dataclass(frozen=True, slots=True, kw_only=True)
class _Disposition:
    attached_pic: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _Stream:
    codec_type: str
    codec_name: str | None = None
    disposition: _Disposition

    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class _Format:
    format_name: str
    size: int
    duration: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class _Probe:
    streams: list[_Stream]
    format: _Format


class FfprobeMediaProber(MediaProber):
    # ffprobe prints the numbers of a format as strings
    _RETORT: ClassVar[Retort] = Retort(strict_coercion=False)

    @override
    async def probe(self, path: Path) -> MediaInfo:
        try:
            output: bytes = await run_process(
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "format=format_name,size,duration:stream=codec_type,codec_name,width,height:stream_disposition=attached_pic",
                "--",
                path,
            )
        except subprocess.CalledProcessError as error:
            raise MediaUnavailableError from error

        probe: _Probe = self._RETORT.load(json.loads(output), _Probe)
        video: _Stream | None = self._find_stream(probe=probe, codec_type="video")
        audio: _Stream | None = self._find_stream(probe=probe, codec_type="audio")

        return MediaInfo(
            kind=self._get_kind(probe=probe, video=video),
            size=probe.format.size,
            container=probe.format.format_name,
            video_codec=video and video.codec_name,
            audio_codec=audio and audio.codec_name,
            duration=probe.format.duration,
            width=video and video.width,
            height=video and video.height,
        )

    @staticmethod
    def _find_stream(*, probe: _Probe, codec_type: str) -> _Stream | None:
        return next(
            (
                stream
                for stream in probe.streams
                # a cover of an audio is a video stream too
                if stream.codec_type == codec_type and not stream.disposition.attached_pic
            ),
            None,
        )

    @staticmethod
    def _get_kind(*, probe: _Probe, video: _Stream | None) -> MediaKind:
        # ffmpeg reads a lone image with `image2` or with a `*_pipe` demuxer of its codec
        if probe.format.format_name == "image2" or probe.format.format_name.endswith("_pipe"):
            return MediaKind.PHOTO

        if video is None:
            return MediaKind.AUDIO

        return MediaKind.VIDEO
