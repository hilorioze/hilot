import logging

from dishka import AsyncContainer

from hilot.application.watermarks.add_account import AddDetectionAccount, AddDetectionAccountDTO

logger: logging.Logger = logging.getLogger(__name__)


async def add_detection_account(
    uid: str, refresh_token: str, *, container: AsyncContainer
) -> None:
    async with container() as request_container:
        interactor: AddDetectionAccount = await request_container.get(AddDetectionAccount)

        if await interactor(AddDetectionAccountDTO(uid=uid, refresh_token=refresh_token)):
            logger.info("added the synthid.com account %s", uid)
