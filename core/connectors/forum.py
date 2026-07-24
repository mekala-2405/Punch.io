"""Forum (Discourse) connector: parse Discourse posts into canonical Messages."""
import html
import os
import re
from html.parser import HTMLParser

import requests

from core.connectors.base import to_iso_utc
from core.message import Message


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _strip_html(text: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(text)
    return html.unescape("".join(extractor.parts)).strip()


class ForumConnector:
    name = "forum"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_username: str | None = None,
        source_id: str | None = None,
    ):
        self.base_url = base_url or os.getenv("FORUM_BASE_URL")
        self.api_key = api_key or os.getenv("FORUM_API_KEY")
        self.api_username = api_username or os.getenv("FORUM_API_USERNAME")
        self._source_id = source_id

    @property
    def source_id(self) -> str:
        if self._source_id is not None:
            return self._source_id
        return f"forum:{self.base_url or ''}"

    def parse(self, raw: list[dict]) -> list[Message]:
        """Pure. Map Discourse-style posts into canonical Messages.

        Skips entries missing id, created_at, or with empty body after HTML stripping.
        """
        messages: list[Message] = []
        for post in raw:
            if post.get("id") is None or not post.get("created_at"):
                continue
            body_html = post.get("cooked")
            if body_html is None:
                body_html = post.get("raw", "")
            content = _strip_html(body_html) if body_html else ""
            if not content:
                continue
            reply_to = post.get("reply_to_post_number")
            messages.append(
                Message(
                    external_id=str(post["id"]),
                    source=self.name,
                    channel=post.get("topic_slug", ""),
                    author=post.get("username", ""),
                    timestamp=to_iso_utc(post["created_at"]),
                    content=content,
                    thread_id=str(post["topic_id"]) if post.get("topic_id") is not None else None,
                    reply_to=str(reply_to) if reply_to is not None else None,
                    project=None,
                    metadata={},
                )
            )
        return messages

    def fetch(self, cursor: str | None) -> tuple[list[dict], str | None]:
        """Network. GET {base_url}/posts.json with Api-Key/Api-Username headers.

        `cursor` is the highest post id already seen; return only posts with id > cursor.
        Returns (raw_posts, new_cursor=str(max id)).
        """
        url = f"{self.base_url.rstrip('/')}/posts.json"
        headers = {
            "Api-Key": self.api_key or "",
            "Api-Username": self.api_username or "",
        }
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        all_posts = resp.json().get("latest_posts", resp.json().get("posts", []))

        if cursor is not None:
            seen = int(cursor)
            all_posts = [p for p in all_posts if int(p.get("id", 0)) > seen]

        new_cursor = None
        if all_posts:
            new_cursor = str(max(int(p.get("id", 0)) for p in all_posts))
        return all_posts, new_cursor
