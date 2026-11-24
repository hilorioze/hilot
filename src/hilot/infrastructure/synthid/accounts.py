import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar

from hilot.domain.errors.watermark import DetectionQuotaExceededError
from hilot.domain.value_objects.media import MediaKind

_logger: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class IDToken:
    uid: str
    value: str

    # monotonic time
    expires_at: float


@dataclass(slots=True, kw_only=True)
class SynthIDAccount:
    refresh_token: str

    id_token: IDToken | None = None

    # synthid keeps a quota of each media kind, the monotonic time each of them resets
    quota_resets: dict[MediaKind, float] = field(default_factory=dict)


class SynthIDAccountPool:
    _RESET_MARGIN: ClassVar[float] = 1
    _MAX_WAIT: ClassVar[float] = 60

    def __init__(self, refresh_tokens: list[str]) -> None:
        self._accounts: list[SynthIDAccount] = [
            SynthIDAccount(refresh_token=refresh_token) for refresh_token in refresh_tokens
        ]

    async def take(self, kind: MediaKind) -> SynthIDAccount:
        while True:
            now: float = time.monotonic()
            account: SynthIDAccount = min(
                self._accounts, key=lambda account: account.quota_resets.get(kind, 0)
            )
            reset: float = account.quota_resets.get(kind, 0)

            if reset <= now:
                # the next take starts from another account, so the quotas run out evenly
                self._accounts.remove(account)
                self._accounts.append(account)

                return account

            # a quota resets daily, so a check waits only for the one about to reset
            if reset - now > self._MAX_WAIT:
                raise DetectionQuotaExceededError(timedelta(seconds=reset - now))

            _logger.info("every account is out of its %s quota for %.0f s", kind, reset - now)

            await asyncio.sleep(reset - now)

    def exhaust(self, *, account: SynthIDAccount, kind: MediaKind, retry_after: timedelta) -> None:
        # synthid resets a quota up to a second after it says
        account.quota_resets[kind] = (
            time.monotonic() + retry_after.total_seconds() + self._RESET_MARGIN
        )
