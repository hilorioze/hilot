from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


@dataclass(frozen=True, slots=True, kw_only=True)
class NatsConfig:
    servers: list[str]
    token: SecretStr
