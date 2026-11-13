from dataclasses import dataclass

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


def get_delivery_route(account_id: AccountId) -> Route:
    return Route(
        task_name="deliver_media",
        # only the bot process holding the account's session can deliver to it
        subject=f"hilot.delivery.{account_id}",
        durable=f"delivery-{account_id}",
    )
