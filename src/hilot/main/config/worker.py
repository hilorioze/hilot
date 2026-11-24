from dataclasses import dataclass, field
from datetime import timedelta

from dature.fields.secret_str import SecretStr

from .check_in import CheckInConfig
from .http import HTTPConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerConfig:
    concurrency: int

    http: HTTPConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BotConfig(WorkerConfig):
    max_message_age: timedelta

    check_ins: list[CheckInConfig] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloaderConfig(WorkerConfig):
    proxy: SecretStr | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectorConfig(WorkerConfig):
    # the devtools address of the browser the attestations come from
    browser_url: str

    proxy: SecretStr | None = None
