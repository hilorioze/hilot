from dishka import Provider, Scope, provide

from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.presentation.telegram.failure_formatter import ChatFailureFormatter


class FormatterProvider(Provider):
    failure_formatter = provide(ChatFailureFormatter, provides=FailureFormatter, scope=Scope.APP)
