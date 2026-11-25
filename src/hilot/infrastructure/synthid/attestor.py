import asyncio
import base64
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.resources import files
from typing import Any, ClassVar

from aiohttp import ClientSession

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.value_objects.media import MediaKind

from .cdp import CDPConnection
from .client import FIREBASE_API_KEY, ORIGIN, DetectionRequest
from .media_types import MEDIA_KINDS

# signs the page in from a refresh token alone, as firebase keeps a session in its indexeddb
_RESTORE_SESSION: str = """
async (row) => {
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open("firebaseLocalStorageDb", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = reject;
  });
  const transaction = db.transaction("firebaseLocalStorage", "readwrite");
  transaction.objectStore("firebaseLocalStorage").put(row);
  await new Promise((resolve) => (transaction.oncomplete = resolve));
}
"""

# the page asks a browser to agree to its terms before the first detection, and keeps on detecting after the agreement
_AGREE_TO_TERMS: str = """
new MutationObserver(() => document.querySelector("terms-of-service .agree-btn")?.click()).observe(document, {
  childList: true,
  subtree: true,
});
"""

# the page renders its file input after loading
_WAIT_FOR_FILE_INPUT: str = """
new Promise((resolve) => {
  const resolveOnInput = () => document.querySelector("input[type=file]") && resolve();
  new MutationObserver(resolveOnInput).observe(document, { childList: true, subtree: true });
  resolveOnInput();
})
"""

# hands a file to the page as if it was dropped
_DROP_FILE: str = """
(content, mimeType) => {
  const bytes = Uint8Array.from(atob(content), (character) => character.charCodeAt(0));
  const transfer = new DataTransfer();
  transfer.items.add(new File([bytes], "media", { type: mimeType }));
  const input = document.querySelector("input[type=file]");
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
}
"""


class SynthIDAttestor:
    # the page decodes an audio or a video before its upload, but takes any bytes as an image
    _DUMMIES: ClassVar[dict[MediaKind, str]] = {
        MediaKind.PHOTO: "dummy.png",
        MediaKind.AUDIO: "dummy.mp3",
        MediaKind.VIDEO: "dummy.mp4",
    }

    # the page's own cors headers of the upload service, for the faked upload
    _UPLOAD_CORS_HEADERS: ClassVar[dict[str, str]] = {
        "Access-Control-Allow-Origin": ORIGIN,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST, PUT, OPTIONS",
        "Access-Control-Expose-Headers": "X-Goog-Upload-URL, X-Goog-Upload-Status",
    }

    _UPLOAD_URL: ClassVar[str] = "https://content-push.googleapis.com/upload/"
    _DETECTION_URL: ClassVar[str] = f"{ORIGIN}/_/WatermarkApp/data/batchexecute?rpcids=TZRKo"

    # the attestation script loads with the page and needs a moment before it attests anything
    _SETTLE_DELAY: ClassVar[float] = 1.5
    _TIMEOUT: ClassVar[float] = 30

    def __init__(self, *, cdp: CDPConnection, session_id: str) -> None:
        self._cdp: CDPConnection = cdp
        self._session_id: str = session_id

        # one page attests one request at a time
        self._lock: asyncio.Lock = asyncio.Lock()

        self._loaded: asyncio.Event = asyncio.Event()

        # the account the page is signed in to
        self._uid: str | None = None

        self._stored_path: str = ""
        self._detection: asyncio.Future[DetectionRequest] | None = None

        cdp.on("Page.loadEventFired", self._handle_load, session_id=session_id)
        cdp.on("Fetch.requestPaused", self._handle_request, session_id=session_id)

    @classmethod
    @asynccontextmanager
    async def open(
        cls, *, session: ClientSession, cdp_url: str
    ) -> AsyncGenerator[SynthIDAttestor]:
        async with CDPConnection.open(session=session, url=cdp_url) as cdp:
            # a context of its own keeps the page apart from the logins in the browser
            context: dict[str, Any] = await cdp.send(
                "Target.createBrowserContext", {"disposeOnDetach": True}
            )
            target: dict[str, Any] = await cdp.send(
                "Target.createTarget",
                {"url": "about:blank", "browserContextId": context["browserContextId"]},
            )
            attached: dict[str, Any] = await cdp.send(
                "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
            )

            attestor: SynthIDAttestor = cls(cdp=cdp, session_id=attached["sessionId"])
            await attestor._send("Page.enable", {})
            await attestor._send(
                "Page.addScriptToEvaluateOnNewDocument", {"source": _AGREE_TO_TERMS}
            )
            await attestor._send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

            yield attestor

    # the page attests for any account, so it stays signed in to the first one it's given
    async def attest(
        self, *, account: DetectionAccount, mime_type: str, stored_path: str
    ) -> DetectionRequest:
        async with self._lock:
            if self._uid is None:
                await self._sign_in(account)
            else:
                await self._open_page()

            self._stored_path = stored_path
            self._detection = asyncio.get_running_loop().create_future()

            dummy: bytes = (
                files(__package__).joinpath(self._DUMMIES[MEDIA_KINDS[mime_type]]).read_bytes()
            )
            await self._call_function(_DROP_FILE, base64.b64encode(dummy).decode(), mime_type)

            return await asyncio.wait_for(self._detection, self._TIMEOUT)

    # a signed out account signs the page out too, so the next attestation signs in to another one
    def forget(self, uid: str) -> None:
        if self._uid == uid:
            self._uid = None

    async def _sign_in(self, account: DetectionAccount) -> None:
        await self._navigate()
        await self._call_function(
            _RESTORE_SESSION,
            {
                "fbase_key": f"firebase:authUser:{FIREBASE_API_KEY}:[DEFAULT]",
                "value": {
                    "uid": account.uid,
                    # firebase refreshes the missing id token and the rest of the user before using them
                    "stsTokenManager": {
                        "refreshToken": account.refresh_token,
                        "accessToken": None,
                        "expirationTime": 0,
                    },
                    "apiKey": FIREBASE_API_KEY,
                    "appName": "[DEFAULT]",
                    "isAnonymous": False,
                    "emailVerified": True,
                    "providerData": [],
                },
            },
        )

        # firebase reads its session only on loading
        await self._navigate()

        self._uid = account.uid

    async def _open_page(self) -> None:
        # the page shows the last result in place of its file input
        found: dict[str, Any] = await self._evaluate(
            "document.querySelector('input[type=file]') !== null"
        )

        if not found["value"]:
            await self._navigate()

    async def _navigate(self) -> None:
        self._loaded.clear()
        await self._send("Page.navigate", {"url": f"{ORIGIN}/"})

        async with asyncio.timeout(self._TIMEOUT):
            await self._loaded.wait()
            await self._evaluate(_WAIT_FOR_FILE_INPUT)

        await asyncio.sleep(self._SETTLE_DELAY)

    async def _evaluate(self, expression: str) -> dict[str, Any]:
        response: dict[str, Any] = await self._send(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )

        return response["result"]

    async def _call_function(self, function: str, *arguments: object) -> None:
        await self._evaluate(f"({function})(...{json.dumps(arguments)})")

    async def _handle_load(self, _: dict[str, Any]) -> None:
        self._loaded.set()

    async def _handle_request(self, event: dict[str, Any]) -> None:
        url: str = event["request"]["url"]

        if url.startswith(self._UPLOAD_URL):
            await self._fulfill_upload(event)
        elif url.startswith(self._DETECTION_URL) and self._detection is not None:
            # the request goes out from the detector with the account's id token instead
            self._detection.set_result(
                DetectionRequest(
                    url=url,
                    headers=self._read_headers(event),
                    body=event["request"]["postData"],
                )
            )
            self._detection = None

            await self._send(
                "Fetch.failRequest", {"requestId": event["requestId"], "errorReason": "Aborted"}
            )
        else:
            await self._send("Fetch.continueRequest", {"requestId": event["requestId"]})

    async def _fulfill_upload(self, event: dict[str, Any]) -> None:
        # the detector uploads the media itself, the page only needs the path it got
        request_headers: dict[str, str] = self._read_headers(event)
        headers: dict[str, str] = dict(self._UPLOAD_CORS_HEADERS)
        body: str = ""

        if event["request"]["method"] == "OPTIONS":
            headers["Access-Control-Allow-Headers"] = request_headers[
                "access-control-request-headers"
            ]
        elif request_headers["x-goog-upload-command"] == "start":
            headers["X-Goog-Upload-Status"] = "active"
            headers["X-Goog-Upload-URL"] = f"{self._UPLOAD_URL}?upload_id=attestation"
        else:
            headers["X-Goog-Upload-Status"] = "final"
            body = self._stored_path

        await self._send(
            "Fetch.fulfillRequest",
            {
                "requestId": event["requestId"],
                "responseCode": 200,
                "responseHeaders": [
                    {"name": name, "value": value} for name, value in headers.items()
                ],
                "body": base64.b64encode(body.encode()).decode(),
            },
        )

    async def _send(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self._cdp.send(method, params, session_id=self._session_id)

    # the page sets the headers in any case
    @staticmethod
    def _read_headers(event: dict[str, Any]) -> dict[str, str]:
        return {name.lower(): value for name, value in event["request"]["headers"].items()}
