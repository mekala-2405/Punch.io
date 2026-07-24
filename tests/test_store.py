"""Acceptance test for T002 — SQLite store.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/store_api.md
"""
import os
import pytest

from core.message import Message
from core import store


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "sub" / "punch.db")  # nested to test dir creation


def msg(external_id, ts, **kw):
    base = dict(
        external_id=external_id,
        source="discord",
        channel="general",
        author="alice",
        timestamp=ts,
        content=f"message {external_id}",
    )
    base.update(kw)
    return Message(**base)


def test_init_creates_db_and_is_idempotent(db):
    store.init_db(db)
    store.init_db(db)  # second call must not raise
    assert os.path.exists(db)


def test_upsert_returns_new_count_and_dedups(db):
    store.init_db(db)
    batch = [msg("1", "2024-01-01T00:00:00Z"), msg("2", "2024-01-02T00:00:00Z")]
    assert store.upsert_messages(batch, db) == 2
    # re-upsert same -> no new rows
    assert store.upsert_messages(batch, db) == 0
    # one new
    assert store.upsert_messages([msg("3", "2024-01-03T00:00:00Z")], db) == 1


def test_get_messages_ordered_and_filtered(db):
    store.init_db(db)
    store.upsert_messages([
        msg("2", "2024-01-02T00:00:00Z", project="apollo"),
        msg("1", "2024-01-01T00:00:00Z", project="apollo"),
        msg("3", "2024-01-03T00:00:00Z", project="gemini", source="email"),
    ], db)

    all_msgs = store.get_messages(db)
    assert [m.external_id for m in all_msgs] == ["1", "2", "3"]  # timestamp ASC

    apollo = store.get_messages(db, project="apollo")
    assert {m.external_id for m in apollo} == {"1", "2"}

    emails = store.get_messages(db, source="email")
    assert [m.external_id for m in emails] == ["3"]

    windowed = store.get_messages(db, since="2024-01-02T00:00:00Z", until="2024-01-02T23:59:59Z")
    assert [m.external_id for m in windowed] == ["2"]


def test_embedding_tracking(db):
    store.init_db(db)
    store.upsert_messages([
        msg("1", "2024-01-01T00:00:00Z"),
        msg("2", "2024-01-02T00:00:00Z"),
    ], db)

    unembedded = store.get_unembedded(db)
    assert {m.external_id for m in unembedded} == {"1", "2"}

    store.mark_embedded([("discord", "1")], db)
    remaining = store.get_unembedded(db)
    assert [m.external_id for m in remaining] == ["2"]


def test_roundtrip_preserves_fields(db):
    store.init_db(db)
    original = msg("1", "2024-01-01T00:00:00Z", thread_id="t", reply_to="r",
                   project="apollo", metadata={"x": 1})
    store.upsert_messages([original], db)
    loaded = store.get_messages(db)[0]
    assert loaded == original


def test_cursors(db):
    store.init_db(db)
    assert store.get_cursor("discord", db) is None
    store.set_cursor("discord", "12345", db)
    assert store.get_cursor("discord", db) == "12345"
    store.set_cursor("discord", "67890", db)  # upsert
    assert store.get_cursor("discord", db) == "67890"
