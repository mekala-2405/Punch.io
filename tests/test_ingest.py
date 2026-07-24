"""Acceptance test for T005 — incremental ingest pipeline.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/ingest_api.md

The embeddings model is monkeypatched to a tiny deterministic fake so this test runs
OFFLINE and FAST (no MiniLM download, no network). This is why embed_new() must fetch
its embeddings via the module-level get_embeddings() — so we can patch it here.
"""
import os
import pytest

from langchain_core.embeddings import Embeddings

from core.message import Message
from core import store
from ingest import pipeline


class FakeEmbeddings(Embeddings):
    """Deterministic offline stand-in for HuggingFaceEmbeddings.

    Subclasses langchain_core Embeddings so FAISS accepts it (recent langchain
    versions require an Embeddings instance, not just duck-typed methods). Maps text
    to a small fixed-dim vector based on its length and first char code — no model,
    no network.
    """

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
    return {
        "db": str(tmp_path / "punch.db"),
        "faiss": str(tmp_path / "faiss_db"),
    }


def msg(external_id, ts, content=None, **kw):
    base = dict(
        external_id=external_id,
        source="discord",
        channel="general",
        author="alice",
        timestamp=ts,
        content=content or f"message {external_id}",
    )
    base.update(kw)
    return Message(**base)


def test_ingest_new_batch_persists_and_embeds(paths):
    store.init_db(paths["db"])
    batch = [msg("1", "2024-01-01T00:00:00Z"), msg("2", "2024-01-02T00:00:00Z")]

    summary = pipeline.ingest_messages(batch, db_path=paths["db"], faiss_dir=paths["faiss"])

    assert summary == {"received": 2, "new": 2, "embedded": 2}
    # everything is now marked embedded
    assert store.get_unembedded(paths["db"]) == []


def test_ingest_is_idempotent(paths):
    store.init_db(paths["db"])
    batch = [msg("1", "2024-01-01T00:00:00Z"), msg("2", "2024-01-02T00:00:00Z")]

    pipeline.ingest_messages(batch, db_path=paths["db"], faiss_dir=paths["faiss"])

    second = pipeline.ingest_messages(batch, db_path=paths["db"], faiss_dir=paths["faiss"])
    assert second == {"received": 2, "new": 0, "embedded": 0}


def test_project_assignment(paths):
    store.init_db(paths["db"])
    # msg 1 has no project; msg 2 already assigned -> must not be overwritten
    batch = [
        msg("1", "2024-01-01T00:00:00Z"),
        msg("2", "2024-01-02T00:00:00Z", project="gemini"),
    ]
    pipeline.ingest_messages(batch, project="apollo", db_path=paths["db"], faiss_dir=paths["faiss"])

    apollo = {m.external_id for m in store.get_messages(paths["db"], project="apollo")}
    gemini = {m.external_id for m in store.get_messages(paths["db"], project="gemini")}
    assert apollo == {"1"}
    assert gemini == {"2"}


def test_embed_new_creates_then_appends_faiss(paths):
    store.init_db(paths["db"])

    # first batch -> index created on disk
    store.upsert_messages([msg("1", "2024-01-01T00:00:00Z")], paths["db"])
    n1 = pipeline.embed_new(db_path=paths["db"], faiss_dir=paths["faiss"])
    assert n1 == 1
    assert os.path.exists(os.path.join(paths["faiss"], "index.faiss"))

    # second batch -> index loaded and appended, only the new one embedded
    store.upsert_messages([msg("2", "2024-01-02T00:00:00Z")], paths["db"])
    n2 = pipeline.embed_new(db_path=paths["db"], faiss_dir=paths["faiss"])
    assert n2 == 1

    # nothing left unembedded, and a third call embeds nothing
    assert store.get_unembedded(paths["db"]) == []
    assert pipeline.embed_new(db_path=paths["db"], faiss_dir=paths["faiss"]) == 0


def test_embed_new_index_is_searchable(paths):
    """The built index must actually be queryable with the same embeddings."""
    from langchain_community.vectorstores import FAISS

    store.init_db(paths["db"])
    store.upsert_messages([
        msg("1", "2024-01-01T00:00:00Z", content="deployment pipeline broke"),
        msg("2", "2024-01-02T00:00:00Z", content="lunch plans for friday"),
    ], paths["db"])
    pipeline.embed_new(db_path=paths["db"], faiss_dir=paths["faiss"])

    vs = FAISS.load_local(
        paths["faiss"], FakeEmbeddings(), allow_dangerous_deserialization=True
    )
    hits = vs.similarity_search("deployment pipeline broke", k=1)
    assert len(hits) == 1
    assert hits[0].metadata["external_id"] in {"1", "2"}
    assert hits[0].metadata["source"] == "discord"
