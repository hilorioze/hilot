from contextlib import AbstractAsyncContextManager
from typing import Protocol

from hilot.domain.value_objects.media import MediaKey


class MediaLock(Protocol):
    def acquire(self, media_key: MediaKey) -> AbstractAsyncContextManager[None]: ...
