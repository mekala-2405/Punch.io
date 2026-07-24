"""SQLite structured store for normalized messages and sync cursors."""
import sqlite3
from pathlib import Path

from core.message import Message


def init_db(db_path: str = "data/punch.db") -> None:
    """Create tables if they don't exist. Idempotent. Creates parent dir if missing."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                source      TEXT NOT NULL,
                external_id TEXT NOT NULL,
                channel     TEXT,
                author      TEXT,
                timestamp   TEXT,
                content     TEXT,
                thread_id   TEXT,
                reply_to    TEXT,
                project     TEXT,
                metadata    TEXT,
                embedded    INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (source, external_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cursors (
                source TEXT NOT NULL,
                cursor TEXT,
                PRIMARY KEY (source)
            )
            """
        )
        conn.commit()


def upsert_messages(messages: list[Message], db_path: str = "data/punch.db") -> int:
    """Insert messages, ignoring ones whose (source, external_id) already exist.
    Returns the count of NEWLY inserted rows (not counting duplicates).
    New rows get embedded=0."""
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        for m in messages:
            row = m.to_row()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO messages (
                    source, external_id, channel, author, timestamp, content,
                    thread_id, reply_to, project, metadata, embedded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    row["source"], row["external_id"], row["channel"], row["author"],
                    row["timestamp"], row["content"], row["thread_id"], row["reply_to"],
                    row["project"], row["metadata"],
                ),
            )
            inserted += cur.rowcount
        conn.commit()
    return inserted


def get_messages(
    db_path: str = "data/punch.db",
    project: str | None = None,
    source: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[Message]:
    """Return messages matching all provided filters, ordered by timestamp ascending.
    None filters are ignored. Returns Message objects (via Message.from_row)."""
    query = "SELECT * FROM messages"
    clauses: list[str] = []
    params: list = []
    if project is not None:
        clauses.append("project = ?")
        params.append(project)
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if since is not None:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until is not None:
        clauses.append("timestamp <= ?")
        params.append(until)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY timestamp ASC"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [Message.from_row(dict(r)) for r in rows]


def get_unembedded(db_path: str = "data/punch.db") -> list[Message]:
    """Return all messages with embedded=0, ordered by timestamp ascending."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM messages WHERE embedded = 0 ORDER BY timestamp ASC"
        ).fetchall()
    return [Message.from_row(dict(r)) for r in rows]


def mark_embedded(keys: list[tuple[str, str]], db_path: str = "data/punch.db") -> None:
    """Set embedded=1 for each (source, external_id) in keys."""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "UPDATE messages SET embedded = 1 WHERE source = ? AND external_id = ?",
            list(keys),
        )
        conn.commit()


def get_cursor(source: str, db_path: str = "data/punch.db") -> str | None:
    """Return the saved cursor for a source, or None if never set."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT cursor FROM cursors WHERE source = ?", (source,)
        ).fetchone()
    if row is None:
        return None
    return row[0]


def set_cursor(source: str, cursor: str, db_path: str = "data/punch.db") -> None:
    """Upsert the cursor for a source."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO cursors (source, cursor) VALUES (?, ?) "
            "ON CONFLICT(source) DO UPDATE SET cursor = excluded.cursor",
            (source, cursor),
        )
        conn.commit()
