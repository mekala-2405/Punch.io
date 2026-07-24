"""Acceptance test for T007 — Forum (Discourse) connector.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/connector_protocol.md

Only `parse` is tested — it must be PURE. `fetch` hits a live Discourse API and is
exercised manually in the real-world test, not here.
"""
import json
import os

from core.connectors.base import Connector
from core.connectors.forum import ForumConnector
from core.message import Message


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "forum_raw.json")


def load_raw():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_is_a_connector():
    assert isinstance(ForumConnector(), Connector)
    assert ForumConnector().name == "forum"


def test_parse_skips_empty_content():
    msgs = ForumConnector().parse(load_raw())
    assert all(isinstance(m, Message) for m in msgs)
    # third post has empty raw -> skipped
    assert len(msgs) == 2


def test_parse_field_mapping():
    msgs = ForumConnector().parse(load_raw())
    first = msgs[0]
    assert first.external_id == "101"          # id coerced to str
    assert first.source == "forum"
    assert first.author == "carol"
    assert first.content == "Anyone seen the spec?"
    assert first.channel == "project-spec"      # topic_slug
    assert first.thread_id == "55"              # topic_id coerced to str


def test_parse_timestamp_normalized():
    msgs = ForumConnector().parse(load_raw())
    assert msgs[0].timestamp == "2024-02-01T08:00:00Z"


def test_parse_reply_mapping():
    msgs = ForumConnector().parse(load_raw())
    assert msgs[0].reply_to is None
    assert msgs[1].reply_to == "1"             # reply_to_post_number coerced to str
