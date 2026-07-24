"""Acceptance test for T008 — Mattermost (Discord-like) connector.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/connector_protocol.md

Only `parse` is tested — it must be PURE. `fetch` hits a live Mattermost API and is
exercised manually in the real-world test, not here.
"""
import json
import os

from core.connectors.base import Connector
from core.connectors.mattermost import MattermostConnector
from core.message import Message


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "mattermost_raw.json")


def load_raw():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_is_a_connector():
    assert isinstance(MattermostConnector(), Connector)
    assert MattermostConnector().name == "mattermost"


def test_parse_skips_empty_message():
    msgs = MattermostConnector().parse(load_raw())
    assert all(isinstance(m, Message) for m in msgs)
    # third post has empty message -> skipped
    assert len(msgs) == 2


def test_parse_field_mapping():
    msgs = MattermostConnector().parse(load_raw())
    first = msgs[0]
    assert first.external_id == "abc123"
    assert first.source == "mattermost"
    assert first.author == "user_frank"        # user_id (no username in payload)
    assert first.content == "Standup in 5"
    assert first.channel == "chan_xyz"


def test_parse_epoch_millis_to_iso_utc():
    msgs = MattermostConnector().parse(load_raw())
    # 1705312200000 ms == 2024-01-15T09:50:00Z
    assert msgs[0].timestamp == "2024-01-15T09:50:00Z"


def test_parse_root_id_threading():
    msgs = MattermostConnector().parse(load_raw())
    # root post: empty root_id -> no reply
    assert msgs[0].reply_to is None
    # reply: root_id points to first post
    assert msgs[1].reply_to == "abc123"
