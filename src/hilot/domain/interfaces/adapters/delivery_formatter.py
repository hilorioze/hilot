from typing import Protocol

from hilot.domain.value_objects.download import DeliveredPost
from hilot.domain.value_objects.text import RichText


class DeliveryFormatter(Protocol):
    def format_delivered_post(self, post: DeliveredPost) -> RichText: ...
