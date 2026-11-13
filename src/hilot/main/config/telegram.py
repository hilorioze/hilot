from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class TelegramConfig:
    # only a new login uses them, a session string carries its own
    api_id: int
    api_hash: str

    # telegram's test backend
    test_mode: bool = False

    app_version: str
    package_id: str
    certificate_fingerprint: str

    installer: str

    device_model: str
    system_version: str
    perf_cat: int

    lang_code: str
    system_lang_code: str

    timezone: str
