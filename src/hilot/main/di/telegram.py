from dishka import AnyOf, Provider, Scope, from_context, provide
from pyrogram import Client
from pyrogram.storage.storage import Storage

from hilot.domain.interfaces.adapters.chat_bot import ChatBot
from hilot.domain.interfaces.adapters.messenger import (
    MediaRefresher,
    MediaSender,
    MediaUploader,
    MessageReader,
    ProgressIndicator,
    TextSender,
    UploadLimitReader,
)
from hilot.domain.value_objects.message import AccountId
from hilot.infrastructure.telegram.authorization import Authorization
from hilot.infrastructure.telegram.chat_bot import KurigramChatBot
from hilot.infrastructure.telegram.client import create_client
from hilot.infrastructure.telegram.messenger import KurigramMessenger
from hilot.infrastructure.telegram.storage import SQLStorage
from hilot.main.config.telegram import TelegramConfig


class SessionProvider(Provider):
    authorization = from_context(provides=Authorization, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def get_account_id(self, authorization: Authorization) -> AccountId:
        return AccountId(authorization.user_id)

    storage = provide(SQLStorage, provides=Storage, scope=Scope.APP)


class TelegramProvider(Provider):
    config = from_context(provides=TelegramConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def get_client(self, *, config: TelegramConfig, storage: Storage) -> Client:
        return create_client(
            api_id=config.api_id,
            api_hash=config.api_hash,
            app_version=config.app_version,
            package_id=config.package_id,
            certificate_fingerprint=config.certificate_fingerprint,
            installer=config.installer,
            test_mode=config.test_mode,
            device_model=config.device_model,
            system_version=config.system_version,
            perf_cat=config.perf_cat,
            lang_code=config.lang_code,
            system_lang_code=config.system_lang_code,
            timezone=config.timezone,
            storage=storage,
        )

    messenger = provide(
        KurigramMessenger,
        provides=AnyOf[
            ProgressIndicator,
            MessageReader,
            UploadLimitReader,
            MediaUploader,
            MediaSender,
            MediaRefresher,
            TextSender,
        ],
        scope=Scope.APP,
    )

    chat_bot = provide(KurigramChatBot, provides=ChatBot, scope=Scope.APP)
