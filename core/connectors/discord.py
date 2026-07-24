import os
import requests
from dotenv import load_dotenv, find_dotenv

from core.message import Message
from core.connectors.base import to_iso_utc

load_dotenv(find_dotenv())


class DiscordConnector:
    name = "discord"

    def __init__(self, channel: str = "general",
                 bot_token: str | None = None,
                 channel_id: str | None = None,
                 source_id: str | None = None):
        self.channel = channel
        self.bot_token = bot_token
        self.channel_id = channel_id
        self._source_id = source_id

    @property
    def source_id(self) -> str:
        if self._source_id is not None:
            return self._source_id
        cid = self.channel_id or os.getenv("DISCORD_CHANNEL_ID") or self.channel
        return f"discord:{cid}"

    def parse(self, raw: list[dict]) -> list[Message]:
        result = []
        for msg in raw:
            msg_id = msg.get("id")
            ts = msg.get("timestamp")
            if not msg_id or not ts:
                continue
            content = msg.get("content")
            if not content:
                continue
            author = msg.get("author", {})
            if not isinstance(author, dict):
                author = {}
            author_name = author.get("username", "Unknown")
            reply_to = None
            msg_ref = msg.get("message_reference")
            if msg_ref and isinstance(msg_ref, dict):
                reply_to = msg_ref.get("message_id")
            result.append(Message(
                external_id=msg_id,
                source="discord",
                channel=self.channel,
                author=author_name,
                timestamp=to_iso_utc(ts),
                content=content,
                reply_to=reply_to,
            ))
        return result

    def fetch(self, cursor: str | None) -> tuple[list[dict], str | None]:
        bot_token = self.bot_token or os.getenv("DISCORD_BOT_TOKEN")
        channel_id = self.channel_id or os.getenv("DISCORD_CHANNEL_ID")
        if not bot_token or not channel_id:
            raise ValueError("Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID")
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
        if cursor:
            url += f"&after={cursor}"
        headers = {"Authorization": f"Bot {bot_token}"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch messages: {response.status_code}")
        raw = response.json()
        raw.reverse()
        new_cursor = str(raw[-1]["id"]) if raw else cursor
        return raw, new_cursor
