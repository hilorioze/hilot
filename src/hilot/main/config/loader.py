from datetime import time

import dature
from dature.sources.base import Source
from dature.sources.toml_ import Toml11Source

from .sources import SecretSpecSource


def load_config[T](*, schema: type[T], secrets_scope: str | None = None) -> T:
    # `hilot.toml` from the working directory, or from `~/.config`, `/etc` and `/etc/xdg` in that order
    sources: list[Source] = [Toml11Source(file="hilot.toml")]

    if secrets_scope is not None:
        sources.append(SecretSpecSource(scope=secrets_scope))

    return dature.load(
        *sources,
        schema=schema,
        # the toml of nix has no times, only strings; dature takes a toml time as it is
        type_loaders={time: time.fromisoformat},
    )
