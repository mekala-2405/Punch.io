"""Acceptance test for T004 — Discord connector (parse only; fetch is live-only).

Written by the Orchestrator. Runs against tests/fixtures/discord_raw.json — no network.
Contract: orchestration/contracts/connector_protocol.md
"""
import json
import os
import pytest

from core.connectors.discord import DiscordConnector
from core.connectors.base import Connector
from core.message import Message

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "discord_raw.json")


@pytest.fixture
def raw():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_connector_satisfies_protocol():
    assert isinstance(DiscordConnector(), Connector)


def test_parse_skips_empty_content(raw):
    msgs = DiscordConnector().parse(raw)
    # fixture has 5 entries, one (id 1003) has empty content -> 4 remain
    assert len(msgs) == 4
    assert all(m.content for m in msgs)


def test_parse_fields(raw):
    msgs = DiscordConnector(channel="general").parse(raw)
    first = msgs[0]
    assert first.external_id == "1001"
    assert first.source == "discord"
    assert first.channel == "general"
    assert first.author == "alice"
    assert first.timestamp == "2024-01-15T09:30:00Z"  # normalized, Z-suffixed
    assert "YOLO-Seg" in first.content


def test_parse_reply_to(raw):
    msgs = {m.external_id: m for m in DiscordConnector().parse(raw)}
    assert msgs["1004"].reply_to == "1001"
    assert msgs["1001"].reply_to is None


def test_parse_is_pure_no_mutation(raw):
    before = json.dumps(raw, sort_keys=True)
    DiscordConnector().parse(raw)
    after = json.dumps(raw, sort_keys=True)
    assert before == after  # parse must not mutate its input


def test_parse_tolerates_malformed_entries():
    bad = [
        {"content": "no id or ts"},                       # missing id + timestamp
        {"id": "x", "content": "no ts",                   # missing timestamp
         "author": {"username": "z"}},
        {"id": "ok", "timestamp": "2024-01-15T09:30:00+00:00",
         "content": "good", "author": {"username": "z"}},
    ]
    msgs = DiscordConnector().parse(bad)  # must not raise
    assert [m.external_id for m in msgs] == ["ok"]
