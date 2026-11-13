from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckInConfig:
    bot: str
    command: str
    buttons: list[str]

    # a random moment between them every day, in `telegram.timezone`
    start: time
    end: time
