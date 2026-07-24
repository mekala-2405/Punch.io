"""Acceptance test for T009 — per-instance source_id on every connector.

Written by the Orchestrator. Workers must make this pass without weakening it.
Contract: orchestration/contracts/connector_protocol.md

source_id is the per-INSTANCE identity (e.g. two Discord channels must differ) used
as the cursor key so many channels/servers of the same source type sync independently.
`name` stays the source TYPE ("discord"); `source_id` is unique per instance. All pure,
no network.
"""
from core.connectors.discord import DiscordConnector
from core.connectors.email import EmailConnector
from core.connectors.forum import ForumConnector
from core.connectors.mattermost import MattermostConnector


def test_every_connector_has_source_id():
    for c in (DiscordConnector(), EmailConnector(), ForumConnector(), MattermostConnector()):
        assert isinstance(c.source_id, str) and c.source_id, f"{c.name} missing source_id"


def test_source_id_starts_with_name():
    # source_id must be namespaced by the source type so keys never collide across types
    assert DiscordConnector(channel_id="111").source_id.startswith("discord:")
    assert EmailConnector(mailbox="INBOX").source_id.startswith("email:")
    assert ForumConnector(base_url="https://f.example").source_id.startswith("forum:")
    assert MattermostConnector(channel_id="999").source_id.startswith("mattermost:")


def test_distinct_instances_have_distinct_source_ids():
    # Two Discord channels -> two different cursor keys (the whole point of T009)
    a = DiscordConnector(channel="backend", channel_id="111")
    b = DiscordConnector(channel="frontend", channel_id="222")
    assert a.source_id != b.source_id
    assert a.name == b.name == "discord"  # same TYPE

    # Two mailboxes
    assert EmailConnector(mailbox="INBOX").source_id != EmailConnector(mailbox="Sent").source_id

    # Two mattermost channels
    assert (MattermostConnector(channel_id="a").source_id
            != MattermostConnector(channel_id="b").source_id)


def test_explicit_source_id_override():
    # An explicit source_id kwarg wins, so operators can pin a stable key.
    c = DiscordConnector(channel_id="111", source_id="discord:project-apollo-backend")
    assert c.source_id == "discord:project-apollo-backend"


def test_parse_still_works_after_change():
    # Adding source_id must not break parsing behavior.
    raw = [{
        "id": "1", "timestamp": "2024-01-01T00:00:00.000+00:00",
        "content": "hi", "author": {"username": "alice"},
    }]
    msgs = DiscordConnector(channel="backend", channel_id="111").parse(raw)
    assert len(msgs) == 1
    assert msgs[0].source == "discord"
    assert msgs[0].content == "hi"
