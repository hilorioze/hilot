from dataclasses import dataclass

from hilot.domain.interfaces.adapters.messenger import CommandAnswerer, ProgressIndicator
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.value_objects.watermark import WatermarkReply


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyWatermarkCheckDTO:
    reply: WatermarkReply


class ReplyWatermarkCheck:
    def __init__(
        self,
        *,
        command_answerer: CommandAnswerer,
        progress_indicator: ProgressIndicator,
        watermark_formatter: WatermarkFormatter,
    ) -> None:
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._watermark_formatter: WatermarkFormatter = watermark_formatter

    async def __call__(self, data: ReplyWatermarkCheckDTO) -> None:
        await self._command_answerer.answer_command(
            source=data.reply.source,
            text=self._watermark_formatter.format_outcome(data.reply.outcome),
        )

        # an edit keeps the reactions, so the reaction is taken off after it
        if data.reply.source.allows_reactions():
            await self._progress_indicator.hide_progress(data.reply.source)
