import asyncio
import logging
import random
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dishka import AsyncContainer

from hilot.application.check_ins.check_in import RunCheckIn, RunCheckInDTO
from hilot.domain.value_objects.check_in import CheckIn
from hilot.domain.value_objects.message import AccountId
from hilot.infrastructure.metrics import TASK_FAILURES

logger: logging.Logger = logging.getLogger(__name__)


async def run_check_ins(
    *,
    container: AsyncContainer,
    check_in: CheckIn,
    start: time,
    end: time,
    timezone: ZoneInfo,
) -> None:
    account_id: AccountId = await container.get(AccountId)
    day: date = datetime.now(timezone).date()

    while True:
        moment: datetime = _get_moment(
            seed=f"{account_id}:{check_in.bot}:{day}",
            day=day,
            start=start,
            end=end,
            timezone=timezone,
        )
        day += timedelta(days=1)

        delay: timedelta = moment - datetime.now(UTC)

        if delay < timedelta():
            continue

        await asyncio.sleep(delay.total_seconds())

        try:
            async with container() as request_container:
                interactor: RunCheckIn = await request_container.get(RunCheckIn)
                answer: str | None = await interactor(RunCheckInDTO(check_in=check_in))
        # retry the next day
        except Exception:
            logger.exception("check-in to %s failed", check_in.bot)
            TASK_FAILURES.labels(task="check_in").inc()
        else:
            logger.info("check-in to %s: %s", check_in.bot, answer)


def _get_moment(*, seed: str, day: date, start: time, end: time, timezone: ZoneInfo) -> datetime:
    # seeded with the day, so a restart picks the same moment and doesn't check in twice
    fraction: float = random.Random(seed).random()  # noqa: S311  # a moment, not a secret

    begin: datetime = datetime.combine(day, start, timezone).astimezone(UTC)
    finish: datetime = datetime.combine(day, end, timezone).astimezone(UTC)

    return begin + (finish - begin) * fraction
