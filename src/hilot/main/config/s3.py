from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class S3Config:
    endpoint_url: str
    region: str

    bucket: str

    access_key_id: str
    secret_access_key: SecretStr
