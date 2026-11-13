import base64
import struct
from dataclasses import dataclass
from typing import Self

from pyrogram.storage.storage import Storage


@dataclass(frozen=True, slots=True, kw_only=True)
class Authorization:
    dc_id: int
    api_id: int
    test_mode: bool
    auth_key: bytes
    user_id: int
    is_bot: bool

    @classmethod
    def parse(cls, session_string: str) -> Self:
        dc_id: int
        api_id: int
        test_mode: bool
        auth_key: bytes
        user_id: int
        is_bot: bool
        dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
            Storage.SESSION_STRING_FORMAT,
            # a session string exported by kurigram, without its base64 padding
            base64.urlsafe_b64decode(session_string + "=" * (-len(session_string) % 4)),
        )

        return cls(
            dc_id=dc_id,
            api_id=api_id,
            test_mode=test_mode,
            auth_key=auth_key,
            user_id=user_id,
            is_bot=is_bot,
        )
