"""Acceptance test for T001 — canonical Message dataclass.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/message_schema.md
"""
import json
import pytest

from core.message import Message


def make(**overrides):
    base = dict(
        external_id="abc123",
        source="discord",
        channel="general",
        author="alice",
        timestamp="2024-01-15T09:30:00Z",
        content="hello world",
    )
    base.update(overrides)
    return Message(**base)


def test_construct_minimal():
    m = make()
    assert m.external_id == "abc123"
    assert m.thread_id is None
    assert m.reply_to is None
    assert m.project is None
    assert m.metadata == {}


def test_dedup_key():
    m = make(source="email", external_id="42")
    assert m.dedup_key() == "email:42"


@pytest.mark.parametrize("field_name", ["external_id", "source", "timestamp"])
def test_validation_rejects_empty_required_fields(field_name):
    with pytest.raises(ValueError):
        make(**{field_name: ""})


def test_empty_content_is_allowed():
    m = make(content="")
    assert m.content == ""


def test_to_row_encodes_metadata_as_json_string():
    m = make(metadata={"reactions": 3, "pinned": True})
    row = m.to_row()
    assert isinstance(row["metadata"], str)
    assert json.loads(row["metadata"]) == {"reactions": 3, "pinned": True}
    # non-metadata fields keep their names and values
    assert row["external_id"] == "abc123"
    assert row["source"] == "discord"


def test_roundtrip_to_row_from_row():
    m = make(
        thread_id="t1",
        reply_to="r0",
        project="apollo",
        metadata={"k": [1, 2, 3]},
    )
    row = m.to_row()
    m2 = Message.from_row(row)
    assert m2 == m


def test_from_row_handles_missing_metadata():
    row = make().to_row()
    del row["metadata"]
    m = Message.from_row(row)
    assert m.metadata == {}


def test_from_row_handles_empty_metadata_string():
    row = make().to_row()
    row["metadata"] = ""
    m = Message.from_row(row)
    assert m.metadata == {}
