import hashlib

from hilot.domain.value_objects.message import SourceMessage

# the answer to a message goes apart from the parts of its media, which count from 0
ANSWER_PART: int = -1


# the same part of a message always gets the same random ids, so telegram refuses to send it twice
def get_random_id(*, source: SourceMessage, part: int, index: int) -> int:
    digest: bytes = hashlib.blake2b(
        f"{source.account_id}:{source.chat_id}:{source.message_id}:{part}:{index}".encode(),
        digest_size=8,
    ).digest()

    return int.from_bytes(digest, signed=True)
