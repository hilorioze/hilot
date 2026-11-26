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
from hilot.application.media.report_failure import ReportFailure, ReportFailureDTO
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


@asynccontextmanager
async def _report_failure(
    *, interactor: ReportFailure, request: DownloadRequest
) -> AsyncGenerator[None]:
    try:
        yield
    except NotEnoughSpaceError:
        raise
    # a bug of hilot or of a library still gets the sender a reply, and the task still fails for the alert
    except Exception:
        await interactor(ReportFailureDTO(request=request))

        raise


@inject(patch_module=True)
async def download_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[DownloadMedia],
    failure_reporter: FromDishka[ReportFailure],
    postpone_delay: FromDishka[PostponeDelay],
    context: Annotated[Context, TaskiqDepends()],
) -> None:
    request: DownloadRequest = retort.load(payload, DownloadRequest)

    async with (
        _postpone_without_space(context=context, delay=postpone_delay),
        _report_failure(interactor=failure_reporter, request=request),
    ):
        await interactor(DownloadMediaDTO(request=request))


@inject(patch_module=True)
async def transcode_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[TranscodeMedia],
    failure_reporter: FromDishka[ReportFailure],
    postpone_delay: FromDishka[PostponeDelay],
    context: Annotated[Context, TaskiqDepends()],
) -> None:
    result: DownloadResult = retort.load(payload, DownloadResult)

    async with (
        _postpone_without_space(context=context, delay=postpone_delay),
        _report_failure(interactor=failure_reporter, request=result.request),
    ):
        await interactor(TranscodeMediaDTO(result=result))


@inject(patch_module=True)
async def deliver_media(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[DeliverMedia],
) -> None:
    await interactor(DeliverMediaDTO(result=retort.load(payload, DownloadResult)))
