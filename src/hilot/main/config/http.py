from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class HttpConfig:
    host: str
    port: int
