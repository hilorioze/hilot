from dishka import Provider, Scope, provide

from hilot.domain.interfaces.adapters.caption_formatter import CaptionFormatter
from hilot.domain.interfaces.adapters.delivery_formatter import DeliveryFormatter
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.transcription_formatter import TranscriptionFormatter
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.presentation.telegram.caption_formatter import ChatCaptionFormatter
from hilot.presentation.telegram.delivery_formatter import ChatDeliveryFormatter
from hilot.presentation.telegram.failure_formatter import ChatFailureFormatter
from hilot.presentation.telegram.transcription_formatter import ChatTranscriptionFormatter
from hilot.presentation.telegram.watermark_formatter import ChatWatermarkFormatter


class FormatterProvider(Provider):
    caption_formatter = provide(ChatCaptionFormatter, provides=CaptionFormatter, scope=Scope.APP)
    delivery_formatter = provide(
        ChatDeliveryFormatter, provides=DeliveryFormatter, scope=Scope.APP
    )
    failure_formatter = provide(ChatFailureFormatter, provides=FailureFormatter, scope=Scope.APP)
    watermark_formatter = provide(
        ChatWatermarkFormatter, provides=WatermarkFormatter, scope=Scope.APP
    )
    transcription_formatter = provide(
        ChatTranscriptionFormatter, provides=TranscriptionFormatter, scope=Scope.APP
    )
