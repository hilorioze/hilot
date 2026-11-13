from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pyrogram import Client
from pyrogram.enums import ClientPlatform
from pyrogram.storage.storage import Storage


def create_client(
    *,
    api_id: int,
    api_hash: str,
    app_version: str,
    package_id: str,
    certificate_fingerprint: str,
    installer: str,
    test_mode: bool,
    device_model: str,
    system_version: str,
    perf_cat: int,
    lang_code: str,
    system_lang_code: str,
    timezone: str,
    storage: Storage,
) -> Client:
    return Client(
        name="hilot",
        api_id=api_id,
        api_hash=api_hash,
        app_version=app_version,
        device_model=device_model,
        system_version=system_version,
        lang_pack="android",
        lang_code=lang_code,
        system_lang_code=system_lang_code,
        client_platform=ClientPlatform.ANDROID,
        # in the order of https://github.com/DrKLO/Telegram/blob/7be672ead283d022812d75c729d3a04dd4c2a2c6/TMessagesProj/jni/tgnet/ConnectionsManager.cpp#L3225-L3277
        init_connection_params={
            "data": certificate_fingerprint,
            "installer": installer,
            "package_id": package_id,
            "tz_offset": _get_tz_offset(ZoneInfo(timezone)),
            "perf_cat": perf_cat,
        },
        test_mode=test_mode,
        storage_engine=storage,
        # catch up on the messages sent while the bot was down
        skip_updates=False,
    )


def _get_tz_offset(timezone: ZoneInfo) -> int:
    year: int = datetime.now(timezone).year
    offsets: list[timedelta] = [
        datetime(year, month, 1, tzinfo=UTC) - datetime(year, month, 1, tzinfo=timezone)
        for month in (1, 7)
    ]

    # the offset with daylight saving, as https://github.com/DrKLO/Telegram/blob/7be672ead283d022812d75c729d3a04dd4c2a2c6/TMessagesProj/src/main/java/org/telegram/tgnet/ConnectionsManager.java#L263 sends it all year: the larger of the january and july ones
    return int(max(offsets).total_seconds())
