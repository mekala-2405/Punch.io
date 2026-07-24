"""Incremental ingest pipeline tying connectors, store, and FAISS together."""
import os

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from core.message import Message
from core import store
from processing.build_vector_db import get_embeddings


def ingest_messages(
    messages: list[Message],
    project: str | None = None,
    db_path: str = "data/punch.db",
    faiss_dir: str = "data/faiss_db",
) -> dict:
    """Persist a batch of already-parsed messages, then embed the new ones.

    Steps:
      1. If project is given, set .project on each message that has project=None.
      2. upsert_messages() into SQLite -> get count of newly inserted.
      3. embed_new(db_path, faiss_dir) to push unembedded messages into FAISS and
         mark them embedded.
    Returns a summary dict:
      {"received": int, "new": int, "embedded": int}
    """
    if project is not None:
        for m in messages:
            if m.project is None:
                m.project = project

    received = len(messages)
    new = store.upsert_messages(messages, db_path)
    embedded = embed_new(db_path, faiss_dir)
    return {"received": received, "new": new, "embedded": embedded}


def embed_new(db_path: str = "data/punch.db", faiss_dir: str = "data/faiss_db") -> int:
    """Embed every message with embedded=0, upsert into the FAISS index on disk
    (create the index if it doesn't exist, otherwise load and add to it), then
    mark_embedded on those messages. Returns the number embedded."""
    unembedded = store.get_unembedded(db_path)
    if not unembedded:
        return 0

    embeddings = get_embeddings()
    documents = [
        Document(
            page_content=m.content,
            metadata={
                "external_id": m.external_id,
                "source": m.source,
                "channel": m.channel,
                "author": m.author,
                "timestamp": m.timestamp,
                "thread_id": m.thread_id,
                "project": m.project,
            },
        )
        for m in unembedded
    ]

    os.makedirs(faiss_dir, exist_ok=True)
    index_path = os.path.join(faiss_dir, "index.faiss")
    if os.path.exists(index_path):
        vectorstore = FAISS.load_local(
            faiss_dir, embeddings, allow_dangerous_deserialization=True
        )
        vectorstore.add_documents(documents)
    else:
        vectorstore = FAISS.from_documents(documents=documents, embedding=embeddings)

    vectorstore.save_local(faiss_dir)

    keys = [(m.source, m.external_id) for m in unembedded]
    store.mark_embedded(keys, db_path)
    return len(unembedded)


def sync_source(
    connector,
    project: str | None = None,
    db_path: str = "data/punch.db",
    faiss_dir: str = "data/faiss_db",
) -> dict:
    """Live sync for ONE connector. Cursor is keyed by connector.source_id
    (fall back to connector.name if source_id is missing, for back-compat).
      1. key = getattr(connector, "source_id", None) or connector.name
      2. cursor = get_cursor(key)
      3. raw, new_cursor = connector.fetch(cursor)
      4. messages = connector.parse(raw)
      5. summary = ingest_messages(messages, project, db_path, faiss_dir)
      6. if new_cursor is not None: set_cursor(key, new_cursor)
    Returns the summary dict from ingest_messages."""
    key = getattr(connector, "source_id", None) or connector.name
    cursor = store.get_cursor(key, db_path)
    raw, new_cursor = connector.fetch(cursor)
    messages = connector.parse(raw)
    summary = ingest_messages(messages, project, db_path, faiss_dir)
    if new_cursor is not None:
        store.set_cursor(key, new_cursor, db_path)
    return summary


def sync_all(
    connectors: list,
    project: str | None = None,
    db_path: str = "data/punch.db",
    faiss_dir: str = "data/faiss_db",
) -> dict:
    """Sync many connectors. Returns {source_id: summary_or_error} — one entry per
    connector, keyed by its source_id (fall back to name).
      - Call sync_source(conn, project, db_path, faiss_dir) for each.
      - If one raises, catch it and put {"error": str(exception)} in that connector's
        slot; keep going with the rest. A dead source must NOT stop the others.
    """
    results: dict = {}
    for connector in connectors:
        key = getattr(connector, "source_id", None) or connector.name
        try:
            results[key] = sync_source(connector, project, db_path, faiss_dir)
        except Exception as exc:  # noqa: BLE001 - isolate per-source failures
            results[key] = {"error": str(exc)}
    return results
