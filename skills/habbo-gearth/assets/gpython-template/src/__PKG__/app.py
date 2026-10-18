"""The extension's behaviour: which packets it watches and what it does.

The example feature is a pair of chat commands typed by the user themselves:

* ``!ping``: blocked (nobody else sees it), answered in G-Earth's console.
* ``!say <text>``: blocked, then ``<text>`` is sent as normal chat through the paced
  outbox. Shows blocking, building a packet by name, and safe sending.

Replace them with your own feature, keeping the shape: callbacks parse and queue,
nothing slow or risky happens on G-Python's packet thread.
"""

from __future__ import annotations

import logging
from typing import Any

from .gpython import Direction, HMessage, HPacket
from .guard import guarded, reset_reports
from .outbox import Outbox
from .protocol import ChatMode, build_chat, parse_outgoing_chat, parse_seconds

log = logging.getLogger(__name__)

PREFIX = "!"
# Every packet name this extension intercepts or sends, per direction. Checked against
# G-Earth's catalogue on connect, so a renamed packet shows up as one clear warning.
NEEDS = {
    Direction.TO_SERVER: ("Chat",),
    Direction.TO_CLIENT: ("FloodControl",),
}


class App:
    """Registers intercepts on an ``Extension`` and runs the example commands."""

    def __init__(self, ext: Any, outbox: Outbox | None = None) -> None:
        """Wire up; nothing is sent until :meth:`register` and a game connection.

        Args:
            ext: The G-Python ``Extension`` (or a fake in tests).
            outbox: Paced sender; one sending to the server is made if not given.
        """
        self.ext = ext
        self.outbox = outbox or Outbox(self._send_to_server)
        self.connected = False
        self.client_type: str | None = None

    # --- registration ----------------------------------------------------------

    def register(self) -> None:
        """Register every intercept and event. Call before ``ext.start()``."""
        self.ext.intercept(Direction.TO_SERVER, guarded(self.on_own_chat), "Chat")
        self.ext.intercept(Direction.TO_CLIENT, guarded(self.on_flood_control), "FloodControl")
        self.ext.on_event("connection_start", guarded(self.on_connection_start))
        self.ext.on_event("connection_end", guarded(self.on_connection_end))
        self.ext.on_event("double_click", guarded(self.on_double_click))
        self.outbox.start()

    # --- events ----------------------------------------------------------------

    def on_connection_start(self) -> None:
        """Game connected through G-Earth: packet names are now known."""
        info = self.ext.connection_info or {}
        self.client_type = info.get("client_type")
        self.connected = True
        reset_reports()
        log.info(
            "connected to %s (%s, %s)",
            info.get("host"),
            self.client_type,
            info.get("hotel_version"),
        )
        missing = [
            f"{'out' if d == Direction.TO_SERVER else 'in'}:{n}"
            for d, names in NEEDS.items()
            for n in names
            if not self.known(d, n)
        ]
        if missing:
            self.notice(f"Unknown packet names for this client: {', '.join(missing)}", "red")
        else:
            self.notice("Ready. Type !ping or !say <text>.", "blue")

    def on_connection_end(self) -> None:
        """Game disconnected: drop anything still queued."""
        self.connected = False
        self.outbox.clear()
        log.info("disconnected from the hotel")

    def on_double_click(self) -> None:
        """The user pressed ▶ on the extension in G-Earth."""
        self.notice("Commands: !ping, !say <text>", "blue")

    # --- packets ---------------------------------------------------------------

    def on_own_chat(self, message: HMessage) -> None:
        """The user's own outgoing chat: handle ``!`` commands, pass everything else."""
        chat = parse_outgoing_chat(ChatMode.CHAT, message.packet)
        if not chat.text.startswith(PREFIX):
            return
        message.is_blocked = True  # commands never reach the hotel
        command, _, rest = chat.text[len(PREFIX) :].partition(" ")
        if command == "ping":
            self.notice("pong")
        elif command == "say" and rest.strip():
            self.outbox.enqueue(build_chat(rest.strip()[:100], chat.style, chat.tail or -1))
        else:
            self.notice(f"Unknown command {PREFIX}{command}", "red")

    def on_flood_control(self, message: HMessage) -> None:
        """Habbo flood-muted the user: hold the outbox for that long."""
        seconds = parse_seconds(message.packet)
        self.outbox.pause_for(seconds)
        log.info("flood control: pausing sends for %ds", seconds)

    # --- helpers ---------------------------------------------------------------

    def known(self, direction: Direction, name: str) -> bool:
        """Whether G-Earth's packet catalogue for this client has ``name``."""
        infos = getattr(self.ext, "packet_infos", None) or {}
        return name in infos.get(direction, {})

    def notice(self, text: str, color: str = "black") -> None:
        """A line in G-Earth's extension console (and the log)."""
        log.info("notice: %s", text)
        try:
            self.ext.write_to_console(text, color)
        except Exception:
            log.debug("console write failed", exc_info=True)

    def _send_to_server(self, packet: HPacket) -> None:
        """Called on the outbox thread. G-Earth may still drop it (packet safety)."""
        if not self.connected:
            log.info("not connected; dropped a packet")
            return
        self.ext.send_to_server(packet)
