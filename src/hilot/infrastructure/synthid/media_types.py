from hilot.domain.value_objects.media import MediaKind

# the types synthid.com takes, as its page lists them
MEDIA_KINDS: dict[str, MediaKind] = {
    # keep-sorted start
    "audio/aac": MediaKind.AUDIO,
    "audio/flac": MediaKind.AUDIO,
    "audio/mp4": MediaKind.AUDIO,
    "audio/mpeg": MediaKind.AUDIO,
    "audio/ogg": MediaKind.AUDIO,
    "audio/wav": MediaKind.AUDIO,
    "audio/x-m4a": MediaKind.AUDIO,
    "audio/x-wav": MediaKind.AUDIO,
    "image/avif": MediaKind.PHOTO,
    "image/bmp": MediaKind.PHOTO,
    "image/gif": MediaKind.PHOTO,
    "image/heic": MediaKind.PHOTO,
    "image/heif": MediaKind.PHOTO,
    "image/jpeg": MediaKind.PHOTO,
    "image/png": MediaKind.PHOTO,
    "image/tiff": MediaKind.PHOTO,
    "image/webp": MediaKind.PHOTO,
    "video/mp4": MediaKind.VIDEO,
    "video/quicktime": MediaKind.VIDEO,
    "video/webm": MediaKind.VIDEO,
    # keep-sorted end
}
