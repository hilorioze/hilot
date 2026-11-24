from typing import Any

from adaptix import Retort
from dishka.integrations.taskiq import FromDishka, inject

from hilot.application.watermarks.check import CheckWatermark, CheckWatermarkDTO
from hilot.application.watermarks.reply import ReplyWatermarkCheck, ReplyWatermarkCheckDTO
from hilot.application.watermarks.report_failure import (
    ReportWatermarkFailure,
    ReportWatermarkFailureDTO,
)
from hilot.domain.value_objects.watermark import WatermarkCheckRequest, WatermarkReply


@inject(patch_module=True)
async def check_watermark(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[CheckWatermark],
    failure_reporter: FromDishka[ReportWatermarkFailure],
) -> None:
    request: WatermarkCheckRequest = retort.load(payload, WatermarkCheckRequest)

    try:
        await interactor(CheckWatermarkDTO(request=request))
    # a bug of hilot or a change of synthid still gets the command a reply, and the task still fails for the alert
    except Exception:
        await failure_reporter(ReportWatermarkFailureDTO(request=request))

        raise


@inject(patch_module=True)
async def reply_watermark_check(
    *,
    payload: dict[str, Any],
    retort: FromDishka[Retort],
    interactor: FromDishka[ReplyWatermarkCheck],
) -> None:
    await interactor(ReplyWatermarkCheckDTO(reply=retort.load(payload, WatermarkReply)))
