from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


# encrypts the credentials in the database: the cookies and the refresh tokens
@dataclass(frozen=True, slots=True, kw_only=True)
class EncryptionConfig:
    # the first key encrypts and every key decrypts, to rotate keys without losing the credentials
    keys: list[SecretStr]
