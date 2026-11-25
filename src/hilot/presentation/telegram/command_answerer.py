from typing import override

from hilot.domain.interfaces.adapters.messenger import CommandAnswerer, TextEditor, TextReplier
from hilot.domain.value_objects.message import AnswerKind, CommandAnswer, SourceMessage
from hilot.domain.value_objects.text import RichText


class ChatCommandAnswerer(CommandAnswerer):
    def __init__(self, *, text_editor: TextEditor, text_replier: TextReplier) -> None:
        self._text_editor: TextEditor = text_editor
        self._text_replier: TextReplier = text_replier

    @override
    async def answer_command(self, *, source: SourceMessage, answer: CommandAnswer) -> None:
        sections: dict[AnswerKind, list[RichText]] = {}

        for entry in answer.entries:
            sections.setdefault(entry.kind, []).append(entry.text)

        text: RichText = RichText.join(
            separator="\n",
            texts=[
                self._format_section(kind=kind, texts=texts) for kind, texts in sections.items()
            ],
        )

        # the message of the other side can't be edited
        if not source.is_outgoing:
            await self._text_replier.reply_text(source=source, text=text)

            return

        await self._text_editor.edit_text(
            source=source, text=RichText.plain(f"{source.text}\n\n") + text
        )

    # a single entry follows its kind, several go under it one per line
    @staticmethod
    def _format_section(*, kind: AnswerKind, texts: list[RichText]) -> RichText:
        if len(texts) == 1:
            return RichText.plain(f"{kind}: ") + texts[0]

        return RichText.join(separator="\n", texts=[RichText.plain(f"{kind}s:"), *texts])
