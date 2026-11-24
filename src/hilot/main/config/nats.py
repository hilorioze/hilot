from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class NATSConfig:
    servers: list[str]
    token: SecretStr
