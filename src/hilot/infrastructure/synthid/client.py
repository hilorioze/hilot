import asyncio
import json
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, ClassVar

from aiohttp import ClientResponse, ClientSession

from hilot.domain.errors.watermark import DetectionAccountRevokedError
from hilot.domain.value_objects.watermark import WatermarkCheck

from .response import parse_response

# the firebase project of synthid.com
FIREBASE_API_KEY: str = "AIzaSyCjADz3UffE3DF5HZ--7MgVEXrbt6Bgcck"

ORIGIN: str = "https://synthid.com"


@dataclass(frozen=True, slots=True, kw_only=True)
class IDToken:
    value: str

    # monotonic time
    expires_at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectionRequest:
    url: str
    headers: dict[str, str]
    body: str


class SynthIDClient:
    # the page's own credentials of the upload service
    _UPLOAD_HEADERS: ClassVar[dict[str, str]] = {
        "Authorization": "Basic amI5dChNbS0qNjFlczJJVzpyZyRHNUp1QENpV29OJVNS",
        "Push-ID": "feeds/szvztmw263lqqp",
    }

    # the header carrying the id token and the attestation
    _AUTHORIZATION_HEADER: ClassVar[str] = "x-goog-ext-525006476-jspb"

    def __init__(self, session: ClientSession) -> None:
        self._session: ClientSession = session

    async def refresh_id_token(self, refresh_token: str) -> IDToken:
        async with self._session.post(
            "https://securetoken.googleapis.com/v1/token",
            params={"key": FIREBASE_API_KEY},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            # the api key takes requests only from synthid.com
            headers={"Referer": f"{ORIGIN}/"},
        ) as response:
            # firebase answers a revoked refresh token, of a deleted or a disabled account too, with a bad request
            if response.status == HTTPStatus.BAD_REQUEST:
                raise DetectionAccountRevokedError((await response.json())["error"]["message"])

            response.raise_for_status()
            token: dict[str, Any] = await response.json()

        return IDToken(
            value=token["id_token"],
            expires_at=time.monotonic() + int(token["expires_in"]),
        )

    # returns the path of the stored media, which the detection takes
    async def upload(self, *, path: Path, name: str) -> str:
        size: int = (await asyncio.to_thread(path.stat)).st_size
        headers: dict[str, str] = {
            **self._UPLOAD_HEADERS,
            "Push-Filename": name,
            "Origin": ORIGIN,
            "Referer": f"{ORIGIN}/",
        }

        async with self._session.post(
            "https://content-push.googleapis.com/upload/",
            headers={
                **headers,
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Header-Content-Length": str(size),
            },
            raise_for_status=True,
        ) as response:
            upload_url: str = response.headers["X-Goog-Upload-URL"]

        with path.open("rb") as file:
            async with self._session.post(
                upload_url,
                data=file,
                headers={
                    **headers,
                    "X-Goog-Upload-Command": "upload, finalize",
                    "X-Goog-Upload-Offset": "0",
                },
                raise_for_status=True,
            ) as response:
                return await response.text()

    async def detect(self, *, request: DetectionRequest, id_token: IDToken) -> WatermarkCheck:
        # the page's header has its own id token first, the attestation is bound to the body alone
        authorization: list[Any] = json.loads(request.headers[self._AUTHORIZATION_HEADER])
        authorization[0] = id_token.value

        response: ClientResponse
        async with self._session.post(
            request.url,
            data=request.body,
            headers={**request.headers, self._AUTHORIZATION_HEADER: json.dumps(authorization)},
            raise_for_status=True,
        ) as response:
            return parse_response(await response.text())
