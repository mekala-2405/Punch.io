import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv, find_dotenv

from core.message import Message

load_dotenv(find_dotenv())


class MattermostConnector:
    name = "mattermost"

    def __init__(self, channel: str = "town-square",
                 base_url: str | None = None,
                 token: str | None = None,
                 channel_id: str | None = None,
                 source_id: str | None = None):
        self.channel = channel
        self.base_url = base_url
        self.token = token
        self.channel_id_param = channel_id
        self._source_id = source_id

    @property
    def source_id(self) -> str:
        if self._source_id is not None:
            return self._source_id
        cid = self.channel_id_param or os.getenv("MATTERMOST_CHANNEL_ID") or self.channel
        return f"mattermost:{cid}"

    def parse(self, raw: list[dict]) -> list[Message]:
        result = []
        for msg in raw:
            msg_id = msg.get("id")
            create_at = msg.get("create_at")
            if not msg_id or create_at is None:
                continue
            content = msg.get("message")
            if not content:
                continue

            username = msg.get("username")
            user_id = msg.get("user_id", "")
            author = username if username else user_id

            dt = datetime.fromtimestamp(create_at / 1000, tz=timezone.utc)
            timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            root_id = msg.get("root_id") or None
            channel_val = msg.get("channel_id", self.channel)

            result.append(Message(
                external_id=msg_id,
                source="mattermost",
                channel=channel_val,
                author=author,
                timestamp=timestamp,
                content=content,
                thread_id=root_id,
                reply_to=root_id,
            ))
        return result

    def fetch(self, cursor: str | None) -> tuple[list[dict], str | None]:
        base_url = self.base_url or os.getenv("MATTERMOST_URL")
        token = self.token or os.getenv("MATTERMOST_TOKEN")
        channel_id = self.channel_id_param or os.getenv("MATTERMOST_CHANNEL_ID")
        if not base_url or not token or not channel_id:
            raise ValueError("Missing MATTERMOST_URL, MATTERMOST_TOKEN, or MATTERMOST_CHANNEL_ID")
        url = f"{base_url}/api/v4/channels/{channel_id}/posts"
        headers = {"Authorization": f"Bearer {token}"}
        params = {}
        if cursor:
            params["since"] = cursor
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch posts: {response.status_code}")
        body = response.json()
        posts_dict = body.get("posts", {})
        order = body.get("order", [])
        raw = [posts_dict[pid] for pid in order if pid in posts_dict]
        new_cursor = str(max(p["create_at"] for p in raw)) if raw else cursor
        return raw, new_cursor
