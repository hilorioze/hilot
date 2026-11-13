from adaptix.conversion import impl_converter

from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.value_objects.media import StoredMedia
from hilot.domain.value_objects.message import Link


@impl_converter
def convert_stored_media_to_file(media: StoredMedia) -> StoredFile: ...


@impl_converter
def convert_stored_file_to_media(*, stored_file: StoredFile, link: Link) -> StoredMedia: ...
