from dataclasses import dataclass, field
from datetime import datetime

from hilot.domain.value_objects.media import MediaKind


# an account of the watermark detection service, which keeps a quota of each media kind
@dataclass(slots=True, kw_only=True)
class DetectionAccount:
    uid: str

    refresh_token: str = field(compare=False)

    # the moment each exhausted quota resets
    quota_resets: dict[MediaKind, datetime] = field(default_factory=dict, compare=False)

    # the checks take the account used longest ago, so the quotas run out evenly
    used_at: datetime | None = field(default=None, compare=False)

    def has_quota(self, *, kind: MediaKind, now: datetime) -> bool:
        reset: datetime | None = self.quota_resets.get(kind)

        return reset is None or reset <= now
