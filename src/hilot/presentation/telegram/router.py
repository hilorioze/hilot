from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from dishka import AsyncContainer
from pyrogram import Client
from pyrogram.filters import Filter
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from .injection import inject

type MessageCallback = Callable[Concatenate[Client, Message, ...], Coroutine[Any, Any, None]]


# kurigram's decorators need the client at import time; collect the handlers and add them once the container creates it
class Router:
    def __init__(self) -> None:
        self._message_handlers: list[tuple[MessageCallback, Filter]] = []
        self._routers: list[Router] = []

    def on_message(self, filters: Filter) -> Callable[[MessageCallback], MessageCallback]:
        def decorator(callback: MessageCallback) -> MessageCallback:
            self._message_handlers.append((callback, filters))

            return callback

        return decorator

    def include_router(self, router: Router) -> None:
        self._routers.append(router)

    def register(self, *, client: Client, container: AsyncContainer, filters: Filter) -> None:
        # `filters` apply to every handler of the router and of the included ones on top of their own
        for callback, handler_filters in self._message_handlers:
            handler: MessageHandler = MessageHandler(
                inject(func=callback, container=container), handler_filters & filters
            )

            client.add_handler(handler)

        for router in self._routers:
            router.register(client=client, container=container, filters=filters)
