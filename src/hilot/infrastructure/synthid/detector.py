import logging
import time
import uuid
from pathlib import Path
from typing import ClassVar, override

from hilot.domain.interfaces.adapters.watermark_detector import WatermarkDetector
from hilot.domain.value_objects.media import MediaKind
from hilot.domain.value_objects.watermark import WatermarkCheck

from .accounts import IdToken, SynthIdAccount, SynthIdAccountPool
from .attestor import SynthIdAttestor
from .client import DetectionRequest, SynthIdClient
from .errors import QuotaExceededError
from .media_types import MEDIA_KINDS

_logger: logging.Logger = logging.getLogger(__name__)


class SynthIdWatermarkDetector(WatermarkDetector):
    # an id token is refreshed a bit before it expires, so it lasts through the upload
    _ID_TOKEN_MARGIN: ClassVar[float] = 300

    def __init__(
        self, *, client: SynthIdClient, attestor: SynthIdAttestor, account_pool: SynthIdAccountPool
    ) -> None:
        self._client: SynthIdClient = client
        self._attestor: SynthIdAttestor = attestor
        self._account_pool: SynthIdAccountPool = account_pool

    @override
    async def detect(self, *, path: Path, mime_type: str) -> WatermarkCheck:
        kind: MediaKind = MEDIA_KINDS[mime_type]

        while True:
            account: SynthIdAccount = await self._account_pool.take(kind)
            id_token: IdToken = await self._get_id_token(account)

            # the upload keeps the media for a day under a path of the account's own
            stored_path: str = await self._client.upload(
                path=path, name=f"users/{id_token.uid}/files/{uuid.uuid4()}"
            )
            # an attestation expires within minutes, so it's taken only once the media is uploaded
            request: DetectionRequest = await self._attestor.attest(
                mime_type=mime_type, stored_path=stored_path
            )

            try:
                return await self._client.detect(request=request, id_token=id_token)
            except QuotaExceededError as error:
                _logger.info("an account is out of its %s quota for %s", kind, error.retry_after)

                self._account_pool.exhaust(
                    account=account, kind=kind, retry_after=error.retry_after
                )

    async def _get_id_token(self, account: SynthIdAccount) -> IdToken:
        if (
            account.id_token is None
            or account.id_token.expires_at - self._ID_TOKEN_MARGIN < time.monotonic()
        ):
            account.id_token = await self._client.refresh_id_token(account.refresh_token)

        return account.id_token
