from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Cookie:
    domain: str
    path: str
    name: str

    value: str

    expires: int | None
    include_subdomains: bool
    secure: bool
