"""The extension's behaviour with G-Earth faked: no network, no game."""

from __future__ import annotations

import logging

from __PKG__ import guard
from __PKG__.app import App
from __PKG__.gpython import Direction, HPacket
from __PKG__.protocol import ProtocolError


class FakeExtension:
    """Records registrations and sends like G-Python's ``Extension``."""

    def __init__(self, names=None):
        self.intercepts = {}
        self.events = {}
        self.sent = []
        self.console = []
        self.connection_info = {"host": "game-test", "client_type": "FLASH", "hotel_version": "X"}
        self.packet_infos = names or {
            Direction.TO_SERVER: {"Chat": [{"Id": 1}]},
            Direction.TO_CLIENT: {"FloodControl": [{"Id": 2}]},
        }

    def intercept(self, direction, callback, name):
        self.intercepts[(direction, name)] = callback

    def on_event(self, name, callback):
        self.events[name] = callback

    def send_to_server(self, packet):
        self.sent.append(packet)

    def write_to_console(self, text, color="black"):
        self.console.append((text, color))


class FakeOutbox:
    def __init__(self):
        self.items, self.paused = [], 0

    def start(self):
        pass

    def enqueue(self, item):
        self.items.append(item)
        return True

    def pause_for(self, seconds):
        self.paused = seconds

    def clear(self):
        self.items.clear()


class FakeHotel:
    def __init__(self):
        self.sent = []

    def start(self):
        pass

    def send(self, packet):
        self.sent.append(packet)
        return True

    def clear(self):
        self.sent.clear()


class Message:
    def __init__(self, packet):
        self.packet = packet
        self.is_blocked = False


def own_chat(text: str) -> Message:
    pkt = HPacket(1, text, 0, -1)
    pkt.read_index = 6
    return Message(pkt)


def make(names=None, hotel=None):
    ext, outbox = FakeExtension(names), FakeOutbox()
    app = App(ext, outbox, hotel or FakeHotel())
    app.register()
    app.on_connection_start()
    return app, ext, outbox


def test_registers_by_name():
    _, ext, _ = make()
    assert (Direction.TO_SERVER, "Chat") in ext.intercepts
    assert {"connection_start", "connection_end", "double_click"} <= set(ext.events)


def test_ready_notice_when_names_are_known():
    _, ext, _ = make()
    assert ext.console[-1][0].startswith("Ready")


def test_missing_names_are_reported():
    _, ext, _ = make({Direction.TO_SERVER: {}, Direction.TO_CLIENT: {}})
    assert "out:Chat" in ext.console[-1][0] and ext.console[-1][1] == "red"


def test_ping_is_blocked_and_answered():
    _, ext, outbox = make()
    msg = own_chat("!ping")
    ext.intercepts[(Direction.TO_SERVER, "Chat")](msg)
    assert msg.is_blocked and ext.console[-1][0] == "pong" and not outbox.items


def test_say_is_blocked_and_queued_not_sent_directly():
    _, ext, outbox = make()
    msg = own_chat("!say hello there")
    ext.intercepts[(Direction.TO_SERVER, "Chat")](msg)
    assert msg.is_blocked and ext.sent == []  # never sent from the packet thread
    assert len(outbox.items) == 1 and outbox.items[0].incomplete_identifier == "Chat"


def test_help_is_blocked_and_opens_a_popup():
    hotel = FakeHotel()
    _, ext, outbox = make(hotel=hotel)
    msg = own_chat("!help")
    ext.intercepts[(Direction.TO_SERVER, "Chat")](msg)
    assert msg.is_blocked and not outbox.items
    [popup] = hotel.sent
    assert popup.incomplete_identifier == "NotificationDialog"
    assert "<b>!help</b>" in popup.bytearray.decode("utf-8", "replace")


def test_normal_chat_passes_through():
    _, ext, outbox = make()
    msg = own_chat("hello")
    ext.intercepts[(Direction.TO_SERVER, "Chat")](msg)
    assert not msg.is_blocked and not outbox.items


def test_flood_control_pauses_the_outbox():
    _, ext, outbox = make()
    pkt = HPacket(2, 30)
    pkt.read_index = 6
    ext.intercepts[(Direction.TO_CLIENT, "FloodControl")](Message(pkt))
    assert outbox.paused == 30


def test_guard_swallows_errors_and_saves_bad_packets(tmp_path, caplog):
    guard.configure_dump_dir(tmp_path)
    guard.reset_reports()

    def broken(message):
        raise ProtocolError("truncated string")

    def crashing(message):
        raise RuntimeError("bug")

    pkt = HPacket(3, 1)
    with caplog.at_level(logging.WARNING):
        guard.guarded(broken)(Message(pkt))  # must not raise
        guard.guarded(crashing)(Message(pkt))
    assert list(tmp_path.glob("broken-*.hex"))
    assert "handler crashing failed" in caplog.text
    guard.configure_dump_dir(None)
