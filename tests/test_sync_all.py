"""Acceptance test for T010 — multi-source sync with per-source_id cursors.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/ingest_api.md

sync_source / sync_all normally hit the network via connector.fetch(). Here we use a
FAKE connector whose fetch() returns canned payloads and records the cursor it was
called with — no network, fully deterministic. The embeddings are monkeypatched to a
tiny offline fake (same approach as test_ingest.py) so nothing downloads a model.
"""
import os

import pytest
from langchain_core.embeddings import Embeddings

from core import store
from ingest import pipeline


class FakeEmbeddings(Embeddings):
    """Deterministic offline stand-in for HuggingFaceEmbeddings."""

    def _vec(self, text: str) -> list[float]:
        h = float(len(text))
        c = float(ord(text[0])) if text else 0.0
        return [h, c, h * 0.5, c * 0.5]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


@pytest.fixture(autouse=True)
def patch_embeddings(monkeypatch):
    monkeypatch.setattr(pipeline, "get_embeddings", lambda: FakeEmbeddings())


@pytest.fixture
def paths(tmp_path):
    return {"db": str(tmp_path / "punch.db"), "faiss": str(tmp_path / "faiss_db")}


class FakeConnector:
    """Stands in for a real connector. parse() is pure; fetch() returns canned raw
    payloads and records the cursor it was handed so we can assert cursor isolation."""

    def __init__(self, name, source_id, payloads_by_cursor):
        self.name = name
        self.source_id = source_id
        self._payloads = payloads_by_cursor   # {cursor_or_None: (raw_list, new_cursor)}
        self.fetch_calls = []

    def fetch(self, cursor):
        self.fetch_calls.append(cursor)
        return self._payloads.get(cursor, ([], cursor))

    def parse(self, raw):
        # raw items are already canonical-shaped dicts -> build Messages directly
        from core.message import Message
        out = []
        for r in raw:
            out.append(Message(
                external_id=r["id"],
                source=self.name,
                channel=r.get("channel", "c"),
                author="a",
                timestamp=r["ts"],
                content=r["content"],
            ))
        return out


def _payload(id_, ts, content="hello"):
    return {"id": id_, "ts": ts, "content": content}


def test_sync_source_keys_cursor_by_source_id(paths):
    store.init_db(paths["db"])
    conn = FakeConnector(
        name="discord",
        source_id="discord:chan-A",
        payloads_by_cursor={None: ([_payload("1", "2024-01-01T00:00:00Z")], "cur-A")},
    )
    pipeline.sync_source(conn, db_path=paths["db"], faiss_dir=paths["faiss"])

    # cursor stored under source_id, NOT the bare name
    assert store.get_cursor("discord:chan-A", paths["db"]) == "cur-A"
    assert store.get_cursor("discord", paths["db"]) is None


def test_two_channels_same_source_do_not_collide(paths):
    store.init_db(paths["db"])
    chan_a = FakeConnector(
        name="discord", source_id="discord:chan-A",
        payloads_by_cursor={None: ([_payload("1", "2024-01-01T00:00:00Z")], "cur-A")},
    )
    chan_b = FakeConnector(
        name="discord", source_id="discord:chan-B",
        payloads_by_cursor={None: ([_payload("2", "2024-01-02T00:00:00Z")], "cur-B")},
    )

    pipeline.sync_source(chan_a, db_path=paths["db"], faiss_dir=paths["faiss"])
    pipeline.sync_source(chan_b, db_path=paths["db"], faiss_dir=paths["faiss"])

    # each channel kept its own cursor — no clobbering
    assert store.get_cursor("discord:chan-A", paths["db"]) == "cur-A"
    assert store.get_cursor("discord:chan-B", paths["db"]) == "cur-B"

    # re-syncing chan_a resumes from cur-A, not chan_b's cursor
    chan_a._payloads = {"cur-A": ([_payload("3", "2024-01-03T00:00:00Z")], "cur-A2")}
    pipeline.sync_source(chan_a, db_path=paths["db"], faiss_dir=paths["faiss"])
    assert chan_a.fetch_calls == [None, "cur-A"]


def test_sync_all_runs_each_connector_and_aggregates(paths):
    store.init_db(paths["db"])
    conns = [
        FakeConnector("discord", "discord:chan-A",
                      {None: ([_payload("1", "2024-01-01T00:00:00Z")], "cur-A")}),
        FakeConnector("email", "email:INBOX",
                      {None: ([_payload("2", "2024-01-02T00:00:00Z")], "cur-E")}),
    ]
    results = pipeline.sync_all(conns, project="apollo",
                                db_path=paths["db"], faiss_dir=paths["faiss"])

    # returns one summary per connector, keyed by source_id
    assert set(results.keys()) == {"discord:chan-A", "email:INBOX"}
    assert results["discord:chan-A"]["new"] == 1
    assert results["email:INBOX"]["new"] == 1

    # both cursors persisted independently
    assert store.get_cursor("discord:chan-A", paths["db"]) == "cur-A"
    assert store.get_cursor("email:INBOX", paths["db"]) == "cur-E"

    # both messages ingested and tagged with the project
    apollo = store.get_messages(paths["db"], project="apollo")
    assert {m.external_id for m in apollo} == {"1", "2"}


def test_sync_all_isolates_failures(paths):
    """One connector raising must not stop the others; its slot reports an error."""
    store.init_db(paths["db"])

    class BoomConnector(FakeConnector):
        def fetch(self, cursor):
            raise RuntimeError("network down")

    good = FakeConnector("email", "email:INBOX",
                         {None: ([_payload("2", "2024-01-02T00:00:00Z")], "cur-E")})
    bad = BoomConnector("discord", "discord:chan-A", {})

    results = pipeline.sync_all([bad, good], db_path=paths["db"], faiss_dir=paths["faiss"])

    # good one still succeeded
    assert results["email:INBOX"]["new"] == 1
    # bad one is reported with an error key, not a crash
    assert "error" in results["discord:chan-A"]
