from dataclasses import dataclass

from dature.fields.secret_str import SecretStr

from .cookies import CookiesConfig
from .database import DatabaseConfig
from .disk import DiskConfig
from .nats import NATSConfig
from .s3 import S3Config
from .synthid import SynthIDConfig
from .telegram import TelegramConfig
from .worker import BotConfig, DetectorConfig, DownloaderConfig, WorkerConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BotSchema:
    session_string: SecretStr

    bot: BotConfig
    telegram: TelegramConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloaderSchema:
    downloader: DownloaderConfig
    disk: DiskConfig
    cookies: CookiesConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscoderSchema:
    transcoder: WorkerConfig
    disk: DiskConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectorSchema:
    detector: DetectorConfig
    synthid: SynthIDConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class CookieImportSchema:
    cookies: CookiesConfig
    database: DatabaseConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginSchema:
    telegram: TelegramConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrateSchema:
    database: DatabaseConfig
