from dataclasses import dataclass, field

from hilot.domain.value_objects.media import FileId, MediaKey, MediaKind, PostDetails
from hilot.domain.value_objects.message import AccountId, ChatId, MessageId


@dataclass(frozen=True, slots=True, kw_only=True)
class CachedFile:
    account_id: AccountId
    media_key: MediaKey

    kind: MediaKind = field(compare=False)
    file_id: FileId = field(compare=False)

    # the message holding the file, to get a fresh file reference from
    chat_id: ChatId = field(compare=False)
    message_id: MessageId = field(compare=False)

    # a cached file goes out again with the caption of its post
    post: PostDetails = field(compare=False)
