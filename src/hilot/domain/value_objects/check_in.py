from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckIn:
    bot: str
    command: str

    # the callback data of the buttons, pressed one after another
    buttons: list[str]
