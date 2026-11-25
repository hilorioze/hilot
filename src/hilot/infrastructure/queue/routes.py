from dataclasses import dataclass, replace

from hilot.domain.value_objects.message import AccountId


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    task_name: str

    subject: str
    durable: str


DOWNLOAD_ROUTE: Route = Route(
    task_name="download_media", subject="hilot.download", durable="download"
)
TRANSCODE_ROUTE: Route = Route(
    task_name="transcode_media", subject="hilot.transcode", durable="transcode"
)
WATERMARK_ROUTE: Route = Route(
    task_name="check_watermark", subject="hilot.watermark", durable="watermark"
)
TRANSCRIPTION_ROUTE: Route = Route(
    task_name="transcribe_speech", subject="hilot.transcription", durable="transcription"
)


def get_delivery_route(account_id: AccountId) -> Route:
    return Route(
        task_name="deliver_media",
        # only the bot process holding the account's session can deliver to it
        subject=f"hilot.delivery.{account_id}",
        durable=f"delivery-{account_id}",
    )


def get_preview_wait_route(account_id: AccountId) -> Route:
    # only the account reads the preview of its message
    return replace(get_delivery_route(account_id), task_name="await_link_preview")


def get_watermark_reply_route(account_id: AccountId) -> Route:
    # only the account can edit its command, so the reply goes through its delivery
    return replace(get_delivery_route(account_id), task_name="reply_watermark_check")


def get_transcription_reply_route(account_id: AccountId) -> Route:
    # only the account can edit its message, so the reply goes through its delivery
    return replace(get_delivery_route(account_id), task_name="reply_transcription")
