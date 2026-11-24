from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class SynthIdConfig:
    # firebase refresh tokens of the accounts, which take turns as their quotas run out
    refresh_tokens: list[SecretStr]
