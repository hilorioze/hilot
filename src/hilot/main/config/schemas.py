from dataclasses import dataclass

from dature.fields.secret_str import SecretStr

from .database import DatabaseConfig
from .disk import DiskConfig
from .encryption import EncryptionConfig
from .groq import GroqConfig
from .inline_bot import InlineBotConfig
from .nats import NATSConfig
from .s3 import S3Config
from .stored_file import StoredFileConfig
from .telegram import TelegramConfig
from .worker import BotConfig, DetectorConfig, DownloaderConfig, WorkerConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class BotSchema:
    session_string: SecretStr

    bot: BotConfig
    telegram: TelegramConfig
    inline_bot: InlineBotConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloaderSchema:
    downloader: DownloaderConfig
    disk: DiskConfig
    stored_file: StoredFileConfig
    encryption: EncryptionConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscoderSchema:
    transcoder: WorkerConfig
    disk: DiskConfig
    stored_file: StoredFileConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectorSchema:
    detector: DetectorConfig
    encryption: EncryptionConfig
    database: DatabaseConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscriberSchema:
    transcriber: WorkerConfig
    groq: GroqConfig
    nats: NATSConfig
    s3: S3Config


@dataclass(frozen=True, slots=True, kw_only=True)
class CookieImportSchema:
    encryption: EncryptionConfig
    database: DatabaseConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanupSchema:
    database: DatabaseConfig
    stored_file: StoredFileConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginSchema:
    telegram: TelegramConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrateSchema:
    database: DatabaseConfig
