from dataclasses import dataclass
from datetime import timedelta

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class S3Config:
    endpoint_url: str
    region: str

    bucket: str

    # how long a sent file is reused by the other accounts; must be a bit shorter than the bucket keeps a file
    reuse_period: timedelta

    access_key_id: str
    secret_access_key: SecretStr
