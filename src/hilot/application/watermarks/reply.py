from dataclasses import dataclass

from hilot.domain.interfaces.adapters.messenger import TextEditor
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.value_objects.watermark import WatermarkReply


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyWatermarkCheckDTO:
    reply: WatermarkReply


class ReplyWatermarkCheck:
    def __init__(
        self, *, text_editor: TextEditor, watermark_formatter: WatermarkFormatter
    ) -> None:
        self._text_editor: TextEditor = text_editor
        self._watermark_formatter: WatermarkFormatter = watermark_formatter

    async def __call__(self, data: ReplyWatermarkCheckDTO) -> None:
        await self._text_editor.edit_text(
            source=data.reply.source,
            text=self._watermark_formatter.format_outcome(data.reply.outcome),
        )
