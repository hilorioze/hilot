from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from dishka import AsyncContainer
from dishka.integrations.base import wrap_injection
from pyrogram import Client


def inject[U, T](
    *,
    func: Callable[Concatenate[Client, U, ...], Coroutine[Any, Any, T]],
    container: AsyncContainer,
) -> Callable[[Client, U], Coroutine[Any, Any, T]]:
    # kurigram calls a handler with the client and the update alone, the rest comes from a request scope opened for the update
    return wrap_injection(
        func=func, container_getter=lambda _, __: container, is_async=True, manage_scope=True
    )
