from dataclasses import dataclass
from datetime import timedelta

from dature.fields.secret_str import SecretStr

from .http import HttpConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkerConfig:
    concurrency: int

    http: HttpConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BotConfig(WorkerConfig):
    max_message_age: timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloaderConfig(WorkerConfig):
    proxy: SecretStr | None = None
