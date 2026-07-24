"""Canonical normalized message record shared across the system."""
from dataclasses import dataclass, field
import json


@dataclass
class Message:
    external_id: str
    source: str
    channel: str
    author: str
    timestamp: str
    content: str
    thread_id: str | None = None
    reply_to: str | None = None
    project: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.external_id:
            raise ValueError("external_id is required")
        if not self.source:
            raise ValueError("source is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")

    def dedup_key(self) -> str:
        return f"{self.source}:{self.external_id}"

    def to_row(self) -> dict:
        return {
            "external_id": self.external_id,
            "source": self.source,
            "channel": self.channel,
            "author": self.author,
            "timestamp": self.timestamp,
            "content": self.content,
            "thread_id": self.thread_id,
            "reply_to": self.reply_to,
            "project": self.project,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_row(cls, row: dict) -> "Message":
        metadata_raw = row.get("metadata", "")
        if not metadata_raw:
            metadata = {}
        else:
            metadata = json.loads(metadata_raw)
        return cls(
            external_id=row["external_id"],
            source=row["source"],
            channel=row["channel"],
            author=row["author"],
            timestamp=row["timestamp"],
            content=row["content"],
            thread_id=row.get("thread_id"),
            reply_to=row.get("reply_to"),
            project=row.get("project"),
            metadata=metadata,
        )
