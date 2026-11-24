from cryptography.fernet import Fernet, MultiFernet
from dishka import Provider, Scope, from_context, provide

from hilot.main.config.encryption import EncryptionConfig


class EncryptionProvider(Provider):
    config = from_context(provides=EncryptionConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def get_fernet(self, config: EncryptionConfig) -> MultiFernet:
        return MultiFernet([Fernet(key.get_secret_value()) for key in config.keys])
