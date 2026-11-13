from dataclasses import dataclass
from importlib.resources import files

import secretspec
from dature.sources.env_ import EnvSource
from dature.type_aliases import ExpandEnvVarsMode, JSONValue
from secretspec import Resolved


@dataclass(kw_only=True, repr=False)
class SecretSpecSource(EnvSource):
    scope: str

    format_name: str = "secretspec"
    location_label: str = "SECRETSPEC"
    expand_env_vars: ExpandEnvVarsMode | None = "disabled"

    def _load(self) -> JSONValue:
        # keep resolved secrets out of the environment inherited by subprocesses
        resolved: Resolved = secretspec.resolve(
            path=str(files("hilot") / "secretspec.toml"), scope=self.scope
        )

        return {name: secret.get for name, secret in resolved.secrets.items()}
