from dataclasses import dataclass

from dature.fields.secret_str import SecretStr


# the bot whose inline results carry the rich messages of the account
@dataclass(frozen=True, slots=True, kw_only=True)
class InlineBotConfig:
    token: SecretStr

    api_url: str

    # a server of its own with `--local`, which takes uploads of up to 2000 MB instead of 50 MB
    local_mode: bool
