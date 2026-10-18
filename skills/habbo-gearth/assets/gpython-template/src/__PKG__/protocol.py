"""Habbo packet parsing and building, by packet NAME, with UTF-8 strings.

Rules this module enforces (each one cost a debugging session somewhere):

* Packets are addressed by name (``"Chat"``), never by header id: ids change with every
  client build and differ between the Windows and macOS clients.
* Habbo strings are UTF-8, but G-Python's ``read_string()`` defaults to Latin-1, so all
  reads go through :class:`Reader`, which also rejects truncated fields.
* Layouts come from HabboPackets / G-Rust, then are confirmed against a live capture:
  the live client sometimes sends more fields than documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gpython import HPacket

UTF8 = "utf-8"


class ProtocolError(ValueError):
    """A packet didn't match the expected layout."""


class Reader:
    """Bounds-checked reads from an ``HPacket`` (payload starts at byte 6)."""

    def __init__(self, packet: HPacket) -> None:
        """Wrap a packet; reading continues from its current position.

        Args:
            packet: The packet to read.
        """
        self.packet = packet

    @property
    def remaining(self) -> int:
        """Bytes left after the read position."""
        return len(self.packet.bytearray) - self.packet.read_index

    def _need(self, n: int, what: str) -> None:
        if self.remaining < n:
            raise ProtocolError(f"truncated {what}")

    def int(self) -> int:
        """Read a signed 32-bit int."""
        self._need(4, "int")
        return self.packet.read_int()

    def short(self) -> int:
        """Read a signed 16-bit short."""
        self._need(2, "short")
        return self.packet.read_short()

    def bool(self) -> bool:
        """Read a 1-byte bool."""
        self._need(1, "bool")
        return self.packet.read_bool()

    def str(self) -> str:
        """Read a u16-length-prefixed UTF-8 string."""
        data, start = self.packet.bytearray, self.packet.read_index
        self._need(2, "string length")
        end = start + 2 + int.from_bytes(data[start : start + 2], "big")
        if end > len(data):
            raise ProtocolError("truncated string")
        self.packet.read_index = end
        return bytes(data[start + 2 : end]).decode(UTF8, errors="replace")


class ChatMode(Enum):
    """How a chat line was sent; the value is the packet name (same in both directions)."""

    CHAT = "Chat"
    SHOUT = "Shout"
    WHISPER = "Whisper"


@dataclass(frozen=True)
class IncomingChat:
    """A chat line from the server (``in:Chat`` / ``Shout`` / ``Whisper``)."""

    mode: ChatMode
    user_index: int  # room index, not the account id
    text: str
    gesture: int
    style: int


@dataclass(frozen=True)
class OutgoingChat:
    """A chat line the user's own client sent (``out:Chat`` / ``Shout`` / ``Whisper``)."""

    mode: ChatMode
    text: str
    style: int
    whisper_target: str | None = None
    tail: int | None = None  # out:Chat's last int; copy it into chats you send


def parse_incoming_chat(mode: ChatMode, packet: HPacket) -> IncomingChat:
    """Parse ``i index, s text, i gesture, i style, i[ssb] links, i trackingId``.

    Args:
        mode: Which packet it came from.
        packet: The packet, read position at the payload.

    Returns:
        The chat line (links and tracking id are skipped).

    Raises:
        ProtocolError: If the packet is shorter than the layout.
    """
    r = Reader(packet)
    index, text, gesture, style = r.int(), r.str(), r.int(), r.int()
    return IncomingChat(mode, index, text, gesture, style)


def parse_outgoing_chat(mode: ChatMode, packet: HPacket) -> OutgoingChat:
    """Parse the user's own ``Chat`` (``s, i, i``), ``Shout`` or ``Whisper`` (``s, i``).

    A whisper's target and message share one string: ``"target message"``.

    Args:
        mode: Which packet it came from.
        packet: The packet, read position at the payload.

    Returns:
        The chat line.

    Raises:
        ProtocolError: If the packet is shorter than the layout.
    """
    r = Reader(packet)
    raw, style = r.str(), r.int()
    if mode is ChatMode.WHISPER:
        target, _, text = raw.partition(" ")
        return OutgoingChat(mode, text, style, whisper_target=target)
    tail = r.int() if mode is ChatMode.CHAT and r.remaining >= 4 else None
    return OutgoingChat(mode, raw, style, tail=tail)


def build_chat(text: str, style: int = 0, tail: int = -1) -> HPacket:
    """``out:Chat``: ``s text, i style, i tail``. Keep text within 100 UTF-16 units."""
    return HPacket(ChatMode.CHAT.value, text, style, tail)


def build_whisper(target: str, text: str, style: int = 0) -> HPacket:
    """``out:Whisper``: one string ``"target message"``, then ``i style``."""
    return HPacket(ChatMode.WHISPER.value, f"{target} {text}", style)


def parse_seconds(packet: HPacket) -> int:
    """``FloodControl`` / ``RemainingMutePeriod``: ``i seconds``."""
    return Reader(packet).int()
