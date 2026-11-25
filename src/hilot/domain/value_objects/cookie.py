from dataclasses import dataclass
from enum import StrEnum


class CookieSource(StrEnum):
    # an export of some sites, which replaces only their cookies
    SITES = "sites"

    # an export of a whole browser, so a site missing from it has been logged out of
    BROWSER = "browser"


@dataclass(frozen=True, slots=True, kw_only=True)
class Cookie:
    domain: str
    path: str
    name: str

    value: str

    expires: int | None
    include_subdomains: bool
    secure: bool
