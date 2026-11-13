from dataclasses import dataclass
from datetime import timedelta

from dature.fields.byte_size import ByteSize


@dataclass(frozen=True, slots=True, kw_only=True)
class DiskConfig:
    min_free_space: ByteSize
    postpone_delay: timedelta
