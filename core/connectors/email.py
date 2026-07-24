import os
import email
import imaplib
from email.utils import parsedate_to_datetime, parseaddr

from core.message import Message
from core.connectors.base import to_iso_utc


class EmailConnector:
    name = "email"

    def __init__(self, mailbox: str = "INBOX",
                 host: str | None = None,
                 user: str | None = None,
                 password: str | None = None,
                 source_id: str | None = None):
        self.mailbox = mailbox
        self.host = host
        self.user = user
        self.password = password
        self._source_id = source_id

    @property
    def source_id(self) -> str:
        if self._source_id is not None:
            return self._source_id
        return f"email:{self.mailbox}"

    def parse(self, raw: list[dict]) -> list[Message]:
        """Pure. Turn raw email dicts into canonical Message objects."""
        result = []
        for entry in raw:
            msg_id = entry.get("message_id")
            date_str = entry.get("date")
            body = entry.get("body")

            if not msg_id or not date_str or not body:
                continue

            from_field = entry.get("from", "")
            display_name, address = parseaddr(from_field)
            author = display_name if display_name else address

            dt = parsedate_to_datetime(date_str)
            timestamp = to_iso_utc(dt.isoformat())

            subject = entry.get("subject", "")
            metadata = {"subject": subject}

            channel = entry.get("folder", self.mailbox)

            reply_to = entry.get("in_reply_to") or None

            result.append(Message(
                external_id=msg_id,
                source="email",
                channel=channel,
                author=author,
                timestamp=timestamp,
                content=body,
                reply_to=reply_to,
                metadata=metadata,
            ))
        return result

    def fetch(self, cursor: str | None) -> tuple[list[dict], str | None]:
        """Network. Fetch unseen messages from an IMAP mailbox."""
        host = self.host or os.getenv("EMAIL_HOST")
        user = self.user or os.getenv("EMAIL_USER")
        password = self.password or os.getenv("EMAIL_PASSWORD")

        if not host or not user or not password:
            raise ValueError("Missing EMAIL_HOST, EMAIL_USER, or EMAIL_PASSWORD")

        conn = imaplib.IMAP4_SSL(host)
        conn.login(user, password)
        conn.select(self.mailbox)

        if cursor:
            uid_range = f"{int(cursor) + 1}:*"
        else:
            uid_range = "1:*"

        status, data = conn.uid("search", None, f"UID {uid_range}")
        uid_list = data[0].split() if data[0] else []

        messages = []
        for uid in uid_list:
            status, msg_data = conn.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_bytes = msg_data[0][1]
            msg = email.message_from_bytes(raw_bytes)

            date_header = msg.get("Date", "")
            dt = parsedate_to_datetime(date_header) if date_header else None
            date_iso = to_iso_utc(dt.isoformat()) if dt else ""

            from_header = msg.get("From", "")
            display_name, address = parseaddr(from_header)
            author = display_name if display_name else address

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")

            messages.append({
                "message_id": msg.get("Message-ID", ""),
                "from": from_header,
                "subject": msg.get("Subject", ""),
                "date": date_iso,
                "body": body,
                "in_reply_to": msg.get("In-Reply-To"),
                "folder": self.mailbox,
            })

        new_cursor = str(uid_list[-1]) if uid_list else cursor
        conn.logout()
        return messages, new_cursor
