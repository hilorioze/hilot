from collections import defaultdict
from datetime import datetime
from typing import override

from cryptography.fernet import MultiFernet
from sqlalchemy import ColumnElement, ScalarResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.interfaces.repositories.detection_account import DetectionAccountRepository
from hilot.domain.value_objects.media import MediaKind
from hilot.infrastructure.database.sql.models.detection_account import (
    DetectionAccountModel,
    DetectionQuotaModel,
)
from hilot.infrastructure.database.sql.upsert import upsert


class SQLDetectionAccountRepository(DetectionAccountRepository):
    def __init__(self, *, session: AsyncSession, fernet: MultiFernet) -> None:
        self._session: AsyncSession = session
        self._fernet: MultiFernet = fernet

    @override
    async def get(self, uid: str) -> DetectionAccount | None:
        accounts: list[DetectionAccount] = await self._select(DetectionAccountModel.uid == uid)

        return accounts[0] if accounts else None

    @override
    async def get_all(self) -> list[DetectionAccount]:
        return await self._select()

    @override
    async def save(self, account: DetectionAccount) -> None:
        await upsert(
            session=self._session,
            model=DetectionAccountModel,
            rows=[
                {
                    "uid": account.uid,
                    "encrypted_refresh_token": self._fernet.encrypt(
                        account.refresh_token.encode()
                    ),
                    "used_at": account.used_at,
                }
            ],
        )

        # the quotas of the account are replaced as a whole
        await self._session.execute(
            delete(DetectionQuotaModel).where(DetectionQuotaModel.uid == account.uid)
        )
        await upsert(
            session=self._session,
            model=DetectionQuotaModel,
            rows=[
                {"uid": account.uid, "kind": kind, "resets_at": resets_at}
                for kind, resets_at in account.quota_resets.items()
            ],
        )

    @override
    async def delete(self, account: DetectionAccount) -> None:
        await self._session.execute(
            delete(DetectionAccountModel).where(DetectionAccountModel.uid == account.uid)
        )

    async def _select(self, *where: ColumnElement[bool]) -> list[DetectionAccount]:
        models: ScalarResult[DetectionAccountModel] = await self._session.scalars(
            select(DetectionAccountModel).where(*where)
        )
        quotas: ScalarResult[DetectionQuotaModel] = await self._session.scalars(
            select(DetectionQuotaModel)
        )
        quota_resets: defaultdict[str, dict[MediaKind, datetime]] = defaultdict(dict)

        for quota in quotas:
            quota_resets[quota.uid][quota.kind] = quota.resets_at

        return [
            DetectionAccount(
                uid=model.uid,
                refresh_token=self._fernet.decrypt(model.encrypted_refresh_token).decode(),
                quota_resets=quota_resets[model.uid],
                used_at=model.used_at,
            )
            for model in models
        ]
