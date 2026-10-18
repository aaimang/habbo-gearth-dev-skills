"""Packet parsing, offline: packets are built from bytes, no G-Earth needed."""

from __future__ import annotations

import pytest

from __PKG__.gpython import HPacket
from __PKG__.protocol import (
    ChatMode,
    ProtocolError,
    build_chat,
    build_whisper,
    parse_incoming_chat,
    parse_outgoing_chat,
)


def packet(*fields: object, header: int = 1) -> HPacket:
    """A packet with a numeric header (names need a live G-Earth catalogue)."""
    pkt = HPacket(header, *fields)
    pkt.read_index = 6
    return pkt


def s(text: str) -> bytes:
    raw = text.encode("utf-8")
    return len(raw).to_bytes(2, "big") + raw


def test_incoming_chat_decodes_utf8():
    pkt = packet(7, "héllo 👋", 0, 2, 0, -1)
    chat = parse_incoming_chat(ChatMode.CHAT, pkt)
    assert chat.user_index == 7 and chat.text == "héllo 👋" and chat.style == 2


def test_truncated_string_is_a_protocol_error():
    pkt = HPacket.from_bytes(b"\x00\x00\x00\x08\x00\x01\x00\x00\x00\x07\x00\x09ab")
    with pytest.raises(ProtocolError):
        parse_incoming_chat(ChatMode.CHAT, pkt)


def test_outgoing_chat_keeps_the_tail():
    chat = parse_outgoing_chat(ChatMode.CHAT, packet("!ping", 0, 5))
    assert chat.text == "!ping" and chat.tail == 5


def test_outgoing_whisper_splits_the_target():
    chat = parse_outgoing_chat(ChatMode.WHISPER, packet("Friend hi there", 0))
    assert chat.whisper_target == "Friend" and chat.text == "hi there"


def test_builders_use_names_and_utf8():
    pkt = build_chat("ok ✓", 0, -1)
    assert pkt.incomplete_identifier == "Chat"  # resolved to an id by G-Earth at send time
    assert s("ok ✓") in bytes(pkt.bytearray)
    assert build_whisper("Friend", "hi").incomplete_identifier == "Whisper"
