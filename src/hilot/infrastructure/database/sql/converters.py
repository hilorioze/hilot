from collections.abc import Callable
from typing import Any

from adaptix import P, Retort, dumper, name_mapping
from adaptix.conversion import ConversionRetort, coercer, get_converter, link_function

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.value_objects.cookie import Cookie
from hilot.domain.value_objects.media import (
    FileId,
    MediaInfo,
    MediaKey,
    MediaKind,
    PostDetails,
    StorageKey,
)
from hilot.domain.value_objects.message import AccountId, ChatId, MessageId

from .models import (
    CachedFileModel,
    CookieModel,
    DeliveredPartModel,
    StoredFileModel,
)


# the post of a file shares its table, where `title` is the title of an audio
def _get_post(model: CachedFileModel | StoredFileModel) -> PostDetails:
    return PostDetails(
        title=model.post_title, description=model.post_description, author=model.post_author
    )


_CONVERTERS: ConversionRetort = ConversionRetort(
    recipe=[
        coercer(int, AccountId, AccountId),
        coercer(int, ChatId, ChatId),
        coercer(int, MessageId, MessageId),
        coercer(str, FileId, FileId),
        coercer(str, StorageKey, StorageKey),
        link_function(get_converter(CachedFileModel, MediaKey), P[CachedFile].media_key),
        link_function(get_converter(CachedFileModel, MediaInfo), P[CachedFile].info),
        link_function(_get_post, P[CachedFile].post),
        link_function(get_converter(StoredFileModel, MediaKey), P[StoredFile].media_key),
        link_function(get_converter(StoredFileModel, MediaInfo), P[StoredFile].info),
        link_function(_get_post, P[StoredFile].post),
    ],
)
_ROW_RETORT: Retort = Retort(
    recipe=[
        name_mapping(CachedFile, skip=["media_key", "info", "post"]),
        name_mapping(StoredFile, skip=["media_key", "info", "post"]),
        name_mapping(
            PostDetails,
            map={
                "title": "post_title",
                "description": "post_description",
                "author": "post_author",
            },
        ),
        name_mapping(Cookie, skip=["value"]),
        # sqlalchemy binds enum members by name, not by value
        dumper(MediaKind, lambda kind: kind),
    ],
)

convert_cached_file_model_to_entity: Callable[[CachedFileModel], CachedFile] = (
    _CONVERTERS.get_converter(CachedFileModel, CachedFile)
)
convert_delivered_part_model_to_entity: Callable[[DeliveredPartModel], DeliveredPart] = (
    _CONVERTERS.get_converter(DeliveredPartModel, DeliveredPart)
)
convert_stored_file_model_to_entity: Callable[[StoredFileModel], StoredFile] = (
    _CONVERTERS.get_converter(StoredFileModel, StoredFile)
)


@_CONVERTERS.impl_converter
def convert_cookie_model_to_entity(*, model: CookieModel, value: str) -> Cookie: ...


def convert_cached_file_entity_to_row(cached_file: CachedFile) -> dict[str, Any]:
    return (
        _ROW_RETORT.dump(cached_file)
        | _ROW_RETORT.dump(cached_file.media_key)
        | _ROW_RETORT.dump(cached_file.info)
        | _ROW_RETORT.dump(cached_file.post)
    )


def convert_delivered_part_entity_to_row(delivered_part: DeliveredPart) -> dict[str, Any]:
    return _ROW_RETORT.dump(delivered_part)


def convert_stored_file_entity_to_row(stored_file: StoredFile) -> dict[str, Any]:
    return (
        _ROW_RETORT.dump(stored_file)
        | _ROW_RETORT.dump(stored_file.media_key)
        | _ROW_RETORT.dump(stored_file.info)
        | _ROW_RETORT.dump(stored_file.post)
    )


def convert_cookie_entity_to_row(*, cookie: Cookie, encrypted_value: bytes) -> dict[str, Any]:
    return _ROW_RETORT.dump(cookie) | {"encrypted_value": encrypted_value}
