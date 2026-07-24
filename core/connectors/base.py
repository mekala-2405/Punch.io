from typing import Protocol, runtime_checkable
from datetime import datetime, timezone

from core.message import Message


@runtime_checkable
class Connector(Protocol):
    name: str

    def parse(self, raw: list[dict]) -> list[Message]:
        ...

    def fetch(self, cursor: str | None) -> tuple[list[dict], str | None]:
        ...


def to_iso_utc(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
