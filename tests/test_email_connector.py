"""Acceptance test for T006 — Email (IMAP) connector.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/connector_protocol.md

Only `parse` is tested here — it must be PURE (no network). `fetch` hits a live IMAP
server and is exercised manually in the real-world test, not here.
"""
import json
import os

from core.connectors.base import Connector
from core.connectors.email import EmailConnector
from core.message import Message


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "email_raw.json")


def load_raw():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_is_a_connector():
    assert isinstance(EmailConnector(), Connector)
    assert EmailConnector().name == "email"


def test_parse_returns_messages():
    msgs = EmailConnector().parse(load_raw())
    assert all(isinstance(m, Message) for m in msgs)
    # third entry has empty message_id -> skipped
    assert len(msgs) == 2


def test_parse_field_mapping():
    msgs = EmailConnector().parse(load_raw())
    first = msgs[0]
    assert first.external_id == "<msg-1@example.com>"
    assert first.source == "email"
    assert first.content == "We ship Friday."
    assert first.channel == "INBOX"
    # author is the display name when present
    assert first.author == "Alice"
    # subject preserved in metadata
    assert first.metadata.get("subject") == "Deploy plan"


def test_parse_timestamp_normalized_to_utc():
    msgs = EmailConnector().parse(load_raw())
    # +0100 must convert to UTC
    assert msgs[1].timestamp == "2024-01-15T10:00:00Z"
    assert msgs[0].timestamp == "2024-01-15T09:30:00Z"


def test_parse_reply_threading():
    msgs = EmailConnector().parse(load_raw())
    assert msgs[0].reply_to is None
    assert msgs[1].reply_to == "<msg-1@example.com>"
