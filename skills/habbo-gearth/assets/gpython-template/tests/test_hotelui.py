"""Client windows: packet layouts, throttling, the queue, the thread and the fallback."""

from __future__ import annotations

import time

from __PKG__ import hotelui
from __PKG__.gpython import Direction, HPacket
from __PKG__.hotelui import (
    HotelNotifier,
    badge,
    build_bubble,
    build_popup,
    clean,
    colour,
    escape,
)


class FakeExtension:
    """Records ``send_to_client``. G-Python 0.1.6 returns None either way."""

    def __init__(self):
        self.packet_infos = {Direction.TO_CLIENT: {"NotificationDialog": [{"Id": 9}]}}
        self.client_sent = []

    def send_to_client(self, packet):
        self.client_sent.append(packet)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def decode(packet: HPacket) -> tuple[str, dict[str, str]]:
    """Read a built ``NotificationDialog`` back: ``s type, i[s key, s value]``."""
    pkt = HPacket.from_bytes(bytes(packet.bytearray))  # header id stays unset (0xFFFF)
    kind = pkt.read_string(encoding="utf-8")
    params = {}
    for _ in range(pkt.read_int()):
        key = pkt.read_string(encoding="utf-8")
        params[key] = pkt.read_string(encoding="utf-8")
    return kind, params


def test_bubble_layout():
    packet = build_bubble("Settings saved.", title="My Extension", image=badge("ADM"))
    assert packet.incomplete_identifier == "NotificationDialog"
    assert decode(packet) == (
        "extension",
        {
            "display": "BUBBLE",
            "message": "My Extension: Settings saved.",
            "image": "${image.library.url}album1584/ADM.gif",
        },
    )


def test_popup_keeps_line_breaks_utf8_and_link():
    packet = build_popup("one\ncafé ✓", title="Hi", link=("https://x.test", "Go"))
    assert decode(packet)[1] == {
        "display": "POP_UP",
        "title": "Hi",
        "message": "one\ncafé ✓",
        "linkUrl": "https://x.test",
        "linkTitle": "Go",
    }


def test_escape_colour_and_clean():
    assert escape('<b>"x" & y</b>') == "&lt;b&gt;&quot;x&quot; &amp; y&lt;/b&gt;"
    assert colour("no", hotelui.RED) == '<font color="#C62828">no</font>'
    assert clean("a\nb\x07c", 50) == "a b c"
    assert clean("a\nb", 50, multiline=True) == "a\nb"
    long = clean("x" * 500, 20)
    assert len(long) == 20 and long.endswith("…")


def make(ext=None, **flags):
    ext = ext or FakeExtension()
    clock, console = Clock(), []
    notifier = HotelNotifier(
        ext,
        enabled=lambda kind: flags.get(kind, True),
        fallback=console.append,
        clock=clock,
        gap_s=0.0,
    )
    return notifier, ext, clock, console


def test_same_bubble_waits_for_the_gap():
    notifier, ext, clock, _ = make()
    assert notifier.notify("cooldown", "wait 9s", key="cd:a")
    assert not notifier.notify("cooldown", "wait 8s", key="cd:a")
    assert notifier.notify("cooldown", "wait 9s", key="cd:b")
    clock.now += 10
    assert notifier.notify("cooldown", "wait 9s", key="cd:a")
    notifier.flush()
    assert len(ext.client_sent) == 3


def test_kind_toggle():
    notifier, _, _, _ = make(cooldown=False)
    assert not notifier.notify("cooldown", "x")
    assert notifier.notify("error", "x")


def test_queue_keeps_the_newest():
    notifier, ext, _, _ = make()
    for i in range(hotelui.QUEUE_MAX + 5):
        notifier.send(build_bubble(f"n{i}"))
    notifier.flush()
    assert len(ext.client_sent) == hotelui.QUEUE_MAX
    assert decode(ext.client_sent[-1])[1]["message"] == f"n{hotelui.QUEUE_MAX + 4}"


def test_unknown_name_falls_back_to_the_console_once_per_session():
    ext = FakeExtension()
    ext.packet_infos = {Direction.TO_CLIENT: {}}
    notifier, _, _, console = make(ext)
    notifier.notify("error", "one")
    notifier.notify("error", "two")
    notifier.flush()
    assert ext.client_sent == [] and len(console) == 1
    assert "NotificationDialog" in console[0]
    notifier.clear()  # new session: report again
    notifier.notify("error", "three")
    notifier.flush()
    assert len(console) == 2


def test_false_return_and_errors_count_as_failures():
    class Refuses(FakeExtension):
        def send_to_client(self, packet):
            return False

    class Broken(FakeExtension):
        def send_to_client(self, packet):
            raise OSError("socket closed")

    for ext in (Refuses(), Broken()):
        notifier, _, _, console = make(ext)
        notifier.notify("error", "x")
        notifier.flush()
        assert len(console) == 1


def test_thread_sends_and_stops():
    notifier, ext, _, _ = make()
    notifier.start()
    assert notifier._thread.name == "ext-notify"
    notifier.notify("config", "saved")
    for _ in range(200):
        if ext.client_sent:
            break
        time.sleep(0.01)
    notifier.stop()
    assert len(ext.client_sent) == 1 and notifier._thread is None
