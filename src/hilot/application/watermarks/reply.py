from dataclasses import dataclass

from hilot.domain.interfaces.adapters.messenger import CommandAnswerer, ProgressIndicator
from hilot.domain.interfaces.adapters.watermark_detector import DetectableMediaMatcher
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.value_objects.message import AnswerEntry, AnswerKind, CommandAnswer
from hilot.domain.value_objects.text import RichText
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
        media_matcher: DetectableMediaMatcher,
    ) -> None:
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._watermark_formatter: WatermarkFormatter = watermark_formatter
        self._media_matcher: DetectableMediaMatcher = media_matcher

    async def __call__(self, data: ReplyWatermarkCheckDTO) -> None:
        await self._command_answerer.answer_command(
            source=data.reply.source,
            answer=CommandAnswer(
                entries=[
                    AnswerEntry(
                        kind=AnswerKind.RESULT if result.is_verdict() else AnswerKind.ERROR,
                        text=RichText.plain(
                            self._watermark_formatter.format_result(
                                result=result, size_limit=self._media_matcher.get_size_limit()
                            )
                        ),
                    )
                    for result in data.reply.results
                ]
            ),
        )

        # an edit keeps the reactions, so the reaction is taken off after it
        if data.reply.source.allows_reactions():
            await self._progress_indicator.hide_progress(data.reply.source)
