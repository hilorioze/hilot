import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any, NewType

from adaptix import Retort
from dishka.integrations.taskiq import FromDishka, inject
from taskiq import Context, TaskiqDepends

from hilot.application.media.deliver import DeliverMedia, DeliverMediaDTO
from hilot.application.media.download import DownloadMedia, DownloadMediaDTO
from hilot.application.media.transcode import TranscodeMedia, TranscodeMediaDTO
from hilot.domain.errors.disk_space import NotEnoughSpaceError
from hilot.domain.value_objects.download import DownloadRequest, DownloadResult

PostponeDelay = NewType("PostponeDelay", timedelta)


@asynccontextmanager
async def _postpone_without_space(
    *, context: Context, delay: PostponeDelay
) -> AsyncGenerator[None]:
    try:
        yield
    except NotEnoughSpaceError:
        # a full disk frees up as the other tasks finish, so the task waits and goes to the end of the queue
        await asyncio.sleep(delay.total_seconds())

        await context.requeue()


@inject(patch_module=True)
async def download_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[DownloadMedia],
    postpone_delay: FromDishka[PostponeDelay],
    context: Annotated[Context, TaskiqDepends()],
) -> None:
    async with _postpone_without_space(context=context, delay=postpone_delay):
        await interactor(DownloadMediaDTO(request=retort.load(payload, DownloadRequest)))


@inject(patch_module=True)
async def transcode_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[TranscodeMedia],
    postpone_delay: FromDishka[PostponeDelay],
    context: Annotated[Context, TaskiqDepends()],
) -> None:
    async with _postpone_without_space(context=context, delay=postpone_delay):
        await interactor(TranscodeMediaDTO(result=retort.load(payload, DownloadResult)))


@inject(patch_module=True)
async def deliver_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[DeliverMedia],
) -> None:
    await interactor(DeliverMediaDTO(result=retort.load(payload, DownloadResult)))
