from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredFileConfig:
    # how long a stored file is reused by the other accounts; must be a bit shorter than the bucket keeps a file
    reuse_period: timedelta
