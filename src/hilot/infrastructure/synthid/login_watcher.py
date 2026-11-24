from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, ClassVar

from aiohttp import ClientSession

from .cdp import CDPConnection, CDPError
from .client import FIREBASE_API_KEY, ORIGIN

type LoginHandler = Callable[[str, str], Coroutine[Any, Any, None]]

# returns the uid and the refresh token of the firebase session row it's called on
_READ_SESSION: str = """
function () {
  return [this.value.uid, this.value.stsTokenManager.refreshToken];
}
"""


# takes the accounts signed in to synthid.com in the browser's own windows
class SynthIDLoginWatcher:
    _DATABASE: ClassVar[str] = "firebaseLocalStorageDb"
    _OBJECT_STORE: ClassVar[str] = "firebaseLocalStorage"
    _SESSION_KEY: ClassVar[str] = f"firebase:authUser:{FIREBASE_API_KEY}:[DEFAULT]"

    def __init__(
        self, *, cdp: CDPConnection, default_context_id: str, on_login: LoginHandler
    ) -> None:
        self._cdp: CDPConnection = cdp
        self._default_context_id: str = default_context_id
        self._on_login: LoginHandler = on_login

        self._session_ids: set[str] = set()

        # firebase writes its session again on every load and token refresh, the same refresh token by the uid
        self._refresh_tokens: dict[str, str] = {}

        cdp.on("Target.attachedToTarget", self._handle_attach)
        cdp.on("Target.detachedFromTarget", self._handle_detach)

    @classmethod
    @asynccontextmanager
    async def open(
        cls, *, session: ClientSession, cdp_url: str, on_login: LoginHandler
    ) -> AsyncGenerator[SynthIDLoginWatcher]:
        async with CDPConnection.open(session=session, url=cdp_url) as cdp:
            contexts: dict[str, Any] = await cdp.send("Target.getBrowserContexts")
            watcher: SynthIDLoginWatcher = cls(
                cdp=cdp, default_context_id=contexts["defaultBrowserContextId"], on_login=on_login
            )

            # attaches to the open pages and to every page opened later
            await cdp.send(
                "Target.setAutoAttach",
                {
                    "autoAttach": True,
                    "waitForDebuggerOnStart": False,
                    "flatten": True,
                    "filter": [{"type": "page"}],
                },
            )

            yield watcher

    async def _handle_attach(self, event: dict[str, Any]) -> None:
        session_id: str = event["sessionId"]

        # the pages of the attestations have a context of their own
        if event["targetInfo"]["browserContextId"] != self._default_context_id:
            await self._cdp.send("Target.detachFromTarget", {"sessionId": session_id})

            return

        self._session_ids.add(session_id)

        async def handle_update(update: dict[str, Any]) -> None:
            await self._handle_update(session_id=session_id, update=update)

        self._cdp.on("Storage.indexedDBContentUpdated", handle_update, session_id=session_id)

        # firebase writes its session on signing in and again as the page loads
        await self._cdp.send(
            "Storage.trackIndexedDBForStorageKey",
            {"storageKey": f"{ORIGIN}/"},
            session_id=session_id,
        )

    async def _handle_detach(self, event: dict[str, Any]) -> None:
        session_id: str = event["sessionId"]

        if session_id in self._session_ids:
            self._session_ids.remove(session_id)
            self._cdp.off("Storage.indexedDBContentUpdated", session_id=session_id)

    async def _handle_update(self, *, session_id: str, update: dict[str, Any]) -> None:
        if (update["databaseName"], update["objectStoreName"]) != (
            self._DATABASE,
            self._OBJECT_STORE,
        ):
            return

        try:
            login: tuple[str, str] | None = await self._read_login(
                session_id=session_id, storage_key=update["storageKey"]
            )
        # a page leaving for another one has no document to read, the next one writes the session again
        except CDPError:
            return

        # signing out deletes the session, while its refresh token stays valid
        if login is None:
            return

        uid, refresh_token = login

        if self._refresh_tokens.get(uid) != refresh_token:
            self._refresh_tokens[uid] = refresh_token

            await self._on_login(uid, refresh_token)

    async def _read_login(self, *, session_id: str, storage_key: str) -> tuple[str, str] | None:
        data: dict[str, Any] = await self._cdp.send(
            "IndexedDB.requestData",
            {
                "storageKey": storage_key,
                "databaseName": self._DATABASE,
                "objectStoreName": self._OBJECT_STORE,
                "keyRange": {
                    "lower": {"type": "string", "string": self._SESSION_KEY},
                    "upper": {"type": "string", "string": self._SESSION_KEY},
                    "lowerOpen": False,
                    "upperOpen": False,
                },
                "skipCount": 0,
                "pageSize": 1,
            },
            session_id=session_id,
        )

        if not data["objectStoreDataEntries"]:
            return None

        session: dict[str, Any] = await self._cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": data["objectStoreDataEntries"][0]["value"]["objectId"],
                "functionDeclaration": _READ_SESSION,
                "returnByValue": True,
            },
            session_id=session_id,
        )
        uid, refresh_token = session["result"]["value"]

        return uid, refresh_token
