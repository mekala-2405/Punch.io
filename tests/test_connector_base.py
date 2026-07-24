"""Acceptance test for T003 — connector protocol + base helpers.

Written by the Orchestrator. Contract: orchestration/contracts/connector_protocol.md
"""
import pytest

from core.connectors.base import Connector, to_iso_utc
from core.message import Message


def test_to_iso_utc_with_microseconds():
    assert to_iso_utc("2024-01-15T09:30:00.000000+00:00") == "2024-01-15T09:30:00Z"


def test_to_iso_utc_without_microseconds():
    assert to_iso_utc("2024-01-15T09:30:00+00:00") == "2024-01-15T09:30:00Z"


def test_to_iso_utc_converts_offset_to_utc():
    # 09:30 at +02:00 is 07:30 UTC
    assert to_iso_utc("2024-01-15T09:30:00+02:00") == "2024-01-15T07:30:00Z"


def test_connector_is_protocol_and_structural():
    # A class that has name/parse/fetch should satisfy the protocol without subclassing.
    class Dummy:
        name = "dummy"

        def parse(self, raw: list[dict]) -> list[Message]:
            return []

        def fetch(self, cursor):
            return [], None

    d = Dummy()
    assert isinstance(d, Connector)  # runtime_checkable protocol
