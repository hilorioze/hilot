import asyncio
import itertools
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

type EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class CdpError(Exception):
    pass


class BrowserClosedError(CdpError):
    pass


# a connection to a browser over the chrome devtools protocol, with flat sessions of its targets
class CdpConnection:
    def __init__(self, websocket: ClientWebSocketResponse) -> None:
        self._websocket: ClientWebSocketResponse = websocket
        self._ids: itertools.count[int] = itertools.count(1)
        self._responses: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._handlers: dict[str, EventHandler] = {}

        # an event handler sends commands itself, so it runs apart from the reading
        self._handler_tasks: set[asyncio.Task[None]] = set()

    @classmethod
    @asynccontextmanager
    async def open(cls, *, session: ClientSession, url: str) -> AsyncGenerator[CdpConnection]:
        async with session.get(f"{url}/json/version", raise_for_status=True) as response:
            version: dict[str, Any] = await response.json()

        # a response of the network domain can be as big as its body
        async with session.ws_connect(
            version["webSocketDebuggerUrl"], max_msg_size=0
        ) as websocket:
            connection: CdpConnection = cls(websocket)

            async with asyncio.TaskGroup() as group:
                reading: asyncio.Task[None] = group.create_task(connection._read())

                try:
                    yield connection
                finally:
                    reading.cancel()

    def on(self, method: str, handler: EventHandler) -> None:
        self._handlers[method] = handler

    async def send(
        self, method: str, params: dict[str, Any] | None = None, *, session_id: str | None = None
    ) -> dict[str, Any]:
        message_id: int = next(self._ids)
        response: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._responses[message_id] = response

        message: dict[str, Any] = {"id": message_id, "method": method, "params": params or {}}

        if session_id is not None:
            message["sessionId"] = session_id

        await self._websocket.send_json(message)

        return await response

    async def _read(self) -> None:
        async for message in self._websocket:
            if message.type != WSMsgType.TEXT:
                break

            data: dict[str, Any] = message.json()

            if "id" in data:
                response: asyncio.Future[dict[str, Any]] = self._responses.pop(data["id"])

                if "error" in data:
                    response.set_exception(CdpError(data["error"]["message"]))
                else:
                    response.set_result(data["result"])
            elif data["method"] in self._handlers:
                task: asyncio.Task[None] = asyncio.create_task(
                    self._handlers[data["method"]](data["params"])
                )
                self._handler_tasks.add(task)
                task.add_done_callback(self._handler_tasks.discard)

        # the browser went away, so nothing can be done without it
        raise BrowserClosedError
