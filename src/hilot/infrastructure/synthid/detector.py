import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, override

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.errors.watermark import DetectionAccountRevokedError, DetectionQuotaExceededError
from hilot.domain.interfaces.adapters.watermark_detector import WatermarkDetector
from hilot.domain.value_objects.watermark import WatermarkCheck

from .attestor import SynthIDAttestor
from .client import DetectionRequest, IDToken, SynthIDClient
from .errors import QuotaExceededError
from .media_types import MEDIA_KINDS

_logger: logging.Logger = logging.getLogger(__name__)


class SynthIDWatermarkDetector(WatermarkDetector):
    # an id token is refreshed a bit before it expires, so it lasts through the upload
    _ID_TOKEN_MARGIN: ClassVar[float] = 300

    # synthid resets a quota up to a second after it says
    _RESET_MARGIN: ClassVar[timedelta] = timedelta(seconds=1)

    def __init__(self, *, client: SynthIDClient, attestor: SynthIDAttestor) -> None:
        self._client: SynthIDClient = client
        self._attestor: SynthIDAttestor = attestor

        # by the uid of the account
        self._id_tokens: dict[str, IDToken] = {}

    @override
    async def detect(
        self, *, account: DetectionAccount, path: Path, mime_type: str
    ) -> WatermarkCheck:
        id_token: IDToken = await self._get_id_token(account)

        # the upload keeps the media for a day under a path of the account's own
        stored_path: str = await self._client.upload(
            path=path, name=f"users/{account.uid}/files/{uuid.uuid4()}"
        )
        # an attestation expires within minutes, so it's taken only once the media is uploaded
        request: DetectionRequest = await self._attestor.attest(
            account=account, mime_type=mime_type, stored_path=stored_path
        )

        try:
            return await self._client.detect(request=request, id_token=id_token)
        except QuotaExceededError as error:
            _logger.info(
                "the account %s is out of its %s quota for %s",
                account.uid,
                MEDIA_KINDS[mime_type],
                error.retry_after,
            )

            raise DetectionQuotaExceededError(error.retry_after + self._RESET_MARGIN) from error

    async def _get_id_token(self, account: DetectionAccount) -> IDToken:
        id_token: IDToken | None = self._id_tokens.get(account.uid)

        if id_token is not None and id_token.expires_at - self._ID_TOKEN_MARGIN > time.monotonic():
            return id_token

        try:
            id_token = await self._client.refresh_id_token(account.refresh_token)
        except DetectionAccountRevokedError as error:
            _logger.warning("the account %s is signed out: %s", account.uid, error)

            self._id_tokens.pop(account.uid, None)
            self._attestor.forget(account.uid)

            raise

        self._id_tokens[account.uid] = id_token

        return id_token
