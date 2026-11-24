from dataclasses import dataclass

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.interfaces.repositories.detection_account import DetectionAccountRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True, kw_only=True)
class AddDetectionAccountDTO:
    uid: str
    refresh_token: str


class AddDetectionAccount:
    def __init__(self, *, account_repository: DetectionAccountRepository, uow: UnitOfWork) -> None:
        self._account_repository: DetectionAccountRepository = account_repository
        self._uow: UnitOfWork = uow

    # returns whether the account is new
    async def __call__(self, data: AddDetectionAccountDTO) -> bool:
        async with self._uow:
            account: DetectionAccount | None = await self._account_repository.get(data.uid)

            if account is None:
                await self._account_repository.save(
                    DetectionAccount(uid=data.uid, refresh_token=data.refresh_token)
                )

                return True

            # signing in again gives a new refresh token, while the quotas stay the account's
            if account.refresh_token != data.refresh_token:
                account.refresh_token = data.refresh_token
                await self._account_repository.save(account)

        return False
