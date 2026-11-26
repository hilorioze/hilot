from collections.abc import Callable
from datetime import datetime
from typing import Any

from adaptix import P, Retort, dumper, name_mapping
from adaptix.conversion import ConversionRetort, coercer, get_converter, link_function

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.cached_transcript import CachedTranscript
from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.entities.telegram_file_hash import TelegramFileHash
from hilot.domain.value_objects.cookie import Cookie
from hilot.domain.value_objects.media import (
    ContentHash,
    FileId,
    FileUniqueId,
    MediaInfo,
    MediaKey,
    MediaKind,
    PostDetails,
    StorageKey,
)
from hilot.domain.value_objects.message import AccountId, ChatId, MessageId
from hilot.domain.value_objects.transcription import Transcript
from hilot.domain.value_objects.watermark import WatermarkCheck

from .models import (
    CachedFileModel,
    CachedTranscriptModel,
    CachedWatermarkCheckModel,
    CookieModel,
    DeliveredPartModel,
    StoredFileModel,
    TelegramFileHashModel,
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
        coercer(str, FileUniqueId, FileUniqueId),
        coercer(str, ContentHash, ContentHash),
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
        # the driver takes a time as is
        dumper(datetime, lambda moment: moment),
    ],
)
# a verdict goes into one json column as a whole
_JSON_RETORT: Retort = Retort()

convert_cached_file_model_to_entity: Callable[[CachedFileModel], CachedFile] = (
    _CONVERTERS.get_converter(CachedFileModel, CachedFile)
)
convert_delivered_part_model_to_entity: Callable[[DeliveredPartModel], DeliveredPart] = (
    _CONVERTERS.get_converter(DeliveredPartModel, DeliveredPart)
)
convert_stored_file_model_to_entity: Callable[[StoredFileModel], StoredFile] = (
    _CONVERTERS.get_converter(StoredFileModel, StoredFile)
)
convert_telegram_file_hash_model_to_entity: Callable[[TelegramFileHashModel], TelegramFileHash] = (
    _CONVERTERS.get_converter(TelegramFileHashModel, TelegramFileHash)
)


def convert_cached_watermark_check_model_to_entity(
    model: CachedWatermarkCheckModel,
) -> CachedWatermarkCheck:
    return CachedWatermarkCheck(
        content_hash=ContentHash(model.content_hash),
        check=_JSON_RETORT.load(model.check, WatermarkCheck),
        checked_at=model.checked_at,
    )


def convert_cached_transcript_model_to_entity(
    *, model: CachedTranscriptModel, text: str
) -> CachedTranscript:
    return CachedTranscript(
        file_unique_id=FileUniqueId(model.file_unique_id),
        transcript=Transcript(text=text),
        cached_at=model.cached_at,
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
    return _ROW_RETORT.dump(delivered_part) | {"expires_at": delivered_part.get_expiry()}


def convert_stored_file_entity_to_row(stored_file: StoredFile) -> dict[str, Any]:
    return (
        _ROW_RETORT.dump(stored_file)
        | _ROW_RETORT.dump(stored_file.media_key)
        | _ROW_RETORT.dump(stored_file.info)
        | _ROW_RETORT.dump(stored_file.post)
    )


def convert_telegram_file_hash_entity_to_row(
    telegram_file_hash: TelegramFileHash,
) -> dict[str, Any]:
    return _ROW_RETORT.dump(telegram_file_hash)


def convert_cookie_entity_to_row(*, cookie: Cookie, encrypted_value: bytes) -> dict[str, Any]:
    return _ROW_RETORT.dump(cookie) | {"encrypted_value": encrypted_value}


def convert_cached_watermark_check_entity_to_row(
    cached_watermark_check: CachedWatermarkCheck,
) -> dict[str, Any]:
    return {
        "content_hash": cached_watermark_check.content_hash,
        "check": _JSON_RETORT.dump(cached_watermark_check.check),
        "checked_at": cached_watermark_check.checked_at,
        "expires_at": cached_watermark_check.get_expiry(),
    }


def convert_cached_transcript_entity_to_row(
    *, cached_transcript: CachedTranscript, encrypted_text: bytes
) -> dict[str, Any]:
    return {
        "file_unique_id": cached_transcript.file_unique_id,
        "encrypted_text": encrypted_text,
        "cached_at": cached_transcript.cached_at,
        "expires_at": cached_transcript.get_expiry(),
    }
