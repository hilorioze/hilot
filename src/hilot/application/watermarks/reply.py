from dataclasses import dataclass

from hilot.domain.interfaces.adapters.messenger import ProgressIndicator, TextEditor
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.value_objects.watermark import WatermarkReply


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyWatermarkCheckDTO:
    reply: WatermarkReply


class ReplyWatermarkCheck:
    def __init__(
        self,
        *,
        text_editor: TextEditor,
        progress_indicator: ProgressIndicator,
        watermark_formatter: WatermarkFormatter,
    ) -> None:
        self._text_editor: TextEditor = text_editor
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._watermark_formatter: WatermarkFormatter = watermark_formatter

    async def __call__(self, data: ReplyWatermarkCheckDTO) -> None:
        await self._text_editor.edit_text(
            source=data.reply.source,
            text=self._watermark_formatter.format_outcome(data.reply.outcome),
        )

        # an edit keeps the reactions, so the reaction is taken off after it
        if data.reply.source.allows_reactions():
            await self._progress_indicator.hide_progress(data.reply.source)
