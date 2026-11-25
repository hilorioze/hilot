from typing import override

from hilot.domain.interfaces.adapters.messenger import CommandAnswerer, TextEditor
from hilot.domain.value_objects.message import CommandAnswer, SourceMessage


class ChatCommandAnswerer(CommandAnswerer):
    def __init__(self, *, text_editor: TextEditor) -> None:
        self._text_editor: TextEditor = text_editor

    @override
    async def answer_command(self, *, source: SourceMessage, answer: CommandAnswer) -> None:
        await self._text_editor.edit_text(
            source=source, text=f"{source.text}\n\n{self._format_answer(answer)}"
        )

    # a single entry follows its kind, several go under it one per line
    @staticmethod
    def _format_answer(answer: CommandAnswer) -> str:
        if len(answer.entries) == 1:
            return f"{answer.kind}: {answer.entries[0]}"

        return "\n".join([f"{answer.kind}s:", *answer.entries])
