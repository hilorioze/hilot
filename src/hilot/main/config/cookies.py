from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class CookiesConfig:
    # the first key encrypts and every key decrypts, to rotate keys without losing the cookies
    keys: list[SecretStr]
