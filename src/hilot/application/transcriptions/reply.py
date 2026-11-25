from dataclasses import dataclass
from typing import ClassVar

from hilot.domain.errors.messenger import RichUnavailableError
from hilot.domain.interfaces.adapters.messenger import (
    CaptionLimitReader,
    CommandAnswerer,
    ProgressIndicator,
    RichLimitReader,
    RichReplier,
    TextEditor,
    TextFileReplier,
    TextLimitReader,
    TextReplier,
)
from hilot.domain.interfaces.adapters.text_measurer import TextMeasurer
from hilot.domain.interfaces.adapters.transcription_formatter import TranscriptionFormatter
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    SourceMessage,
)
from hilot.domain.value_objects.rich import RichMessage
from hilot.domain.value_objects.text import RichText, TextStyle
from hilot.domain.value_objects.transcription import Transcript, TranscriptionReply


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyTranscriptionDTO:
    reply: TranscriptionReply


class ReplyTranscription:
    _FILE_NAME: ClassVar[str] = "transcript.txt"

    def __init__(
        self,
        *,
        command_answerer: CommandAnswerer,
        text_editor: TextEditor,
        text_replier: TextReplier,
        rich_replier: RichReplier,
        text_file_replier: TextFileReplier,
        caption_limit_reader: CaptionLimitReader,
        text_limit_reader: TextLimitReader,
        rich_limit_reader: RichLimitReader,
        text_measurer: TextMeasurer,
        progress_indicator: ProgressIndicator,
        transcription_formatter: TranscriptionFormatter,
    ) -> None:
        self._command_answerer: CommandAnswerer = command_answerer
        self._text_editor: TextEditor = text_editor
        self._text_replier: TextReplier = text_replier
        self._rich_replier: RichReplier = rich_replier
        self._text_file_replier: TextFileReplier = text_file_replier
        self._caption_limit_reader: CaptionLimitReader = caption_limit_reader
        self._text_limit_reader: TextLimitReader = text_limit_reader
        self._rich_limit_reader: RichLimitReader = rich_limit_reader
        self._text_measurer: TextMeasurer = text_measurer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._transcription_formatter: TranscriptionFormatter = transcription_formatter

    async def __call__(self, data: ReplyTranscriptionDTO) -> None:
        source: SourceMessage = data.reply.source

        if isinstance(data.reply.outcome, Transcript):
            await self._place_transcript(source=source, transcript=data.reply.outcome)
        else:
            await self._command_answerer.answer_command(
                source=source,
                answer=CommandAnswer(
                    entries=[
                        AnswerEntry(
                            kind=AnswerKind.ERROR,
                            text=RichText.plain(
                                self._transcription_formatter.format_failure(data.reply.outcome)
                            ),
                        )
                    ]
                ),
            )

        # an edit keeps the reactions, so the reaction is taken off after it
        if source.allows_reactions():
            await self._progress_indicator.hide_progress(source)

    # the owner's message takes the transcript under its text, the others get it in reply, as a rich message when it's long,
    # and one too long even for that or in a chat without the inline bot goes as a file
    async def _place_transcript(self, *, source: SourceMessage, transcript: Transcript) -> None:
        quote: RichText = RichText.styled(transcript.text, style=TextStyle.EXPANDABLE_QUOTE)
        text: RichText = (
            RichText.join(separator="\n\n", texts=[RichText.plain(source.text), quote])
            if source.text
            else quote
        )
        # the text of a media message is its caption
        limit: int = (
            self._caption_limit_reader.get_caption_limit()
            if source.has_media
            else self._text_limit_reader.get_text_limit()
        )

        if source.is_outgoing and self._text_measurer.measure(text.get_text()) <= limit:
            await self._text_editor.edit_text(source=source, text=text)
        elif (
            self._text_measurer.measure(quote.get_text())
            <= self._text_limit_reader.get_text_limit()
        ):
            await self._text_replier.reply_text(source=source, text=quote)
        elif (
            self._text_measurer.measure(quote.get_text())
            <= self._rich_limit_reader.get_rich_text_limit()
        ):
            try:
                await self._rich_replier.reply_rich(
                    source=source, message=RichMessage(media=[], text=quote)
                )
            except RichUnavailableError:
                await self._reply_file(source=source, transcript=transcript)
        else:
            await self._reply_file(source=source, transcript=transcript)

    async def _reply_file(self, *, source: SourceMessage, transcript: Transcript) -> None:
        await self._text_file_replier.reply_text_file(
            source=source, name=self._FILE_NAME, text=transcript.text
        )
