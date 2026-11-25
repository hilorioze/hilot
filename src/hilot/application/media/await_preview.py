import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from hilot.domain.errors.messenger import MessageGoneError
from hilot.domain.interfaces.adapters.messenger import LinkPreviewReader
from hilot.domain.value_objects.download import LINK_PREVIEW_TIMEOUT, DownloadTrigger, PreviewWait
from hilot.domain.value_objects.message import LinkPreview, SourceMessage

from .request_download import RequestDownload, RequestDownloadDTO


@dataclass(frozen=True, slots=True, kw_only=True)
class AwaitLinkPreviewDTO:
    wait: PreviewWait


class AwaitLinkPreview:
    # telegram puts the preview in a couple of seconds after the message
    _POLL_INTERVAL: ClassVar[float] = 1

    def __init__(
        self, *, link_preview_reader: LinkPreviewReader, request_download: RequestDownload
    ) -> None:
        self._link_preview_reader: LinkPreviewReader = link_preview_reader
        self._request_download: RequestDownload = request_download

    async def __call__(self, data: AwaitLinkPreviewDTO) -> None:
        source: SourceMessage = data.wait.source

        # the deadline counts from the message, so a redelivered wait doesn't start over
        try:
            while datetime.now(UTC) < source.sent_at + LINK_PREVIEW_TIMEOUT:
                if not await self._is_pending(source):
                    break

                await asyncio.sleep(self._POLL_INTERVAL)
        # a message deleted while it waits gets nothing
        except MessageGoneError:
            return

        await self._request_download(
            RequestDownloadDTO(
                source=source,
                trigger=DownloadTrigger.LINK,
                links=data.wait.links,
                reply_to=source.message_id,
            )
        )

    async def _is_pending(self, source: SourceMessage) -> bool:
        preview: LinkPreview | None = await self._link_preview_reader.read_link_preview(source)

        return preview is not None and preview.is_pending
