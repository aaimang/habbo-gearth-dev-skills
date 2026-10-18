#!/usr/bin/env python3
"""A stand-in G-Earth for testing an extension end to end, no Habbo needed (stdlib only).

Speaks G-Earth's extension protocol (as implemented by G-Python 0.1.6 and G-Earth
1.5.x): asks for the extension's info, initialises it, announces a game connection
with a packet catalogue, sends packets through the extension's intercepts, records
what it answers or sends, then closes the socket and checks the process exits (a
G-ExtensionStore requirement).

Usage::

    fake_gearth.py --run "uv run python -m my_ext -p {port} -c COOKIE -f test" \
        --packet 'out:Chat=2096' --packet 'in:FloodControl=1199' \
        --intercept '{out:Chat}{s:"!ping"}{i:0}{i:-1}' \
        --intercept '{out:Chat}{s:"hello"}{i:0}{i:-1}'

    fake_gearth.py --port 9092 --wait          # then start the extension yourself

``--intercept`` takes G-Earth packet expressions: ``{in:Name}`` / ``{out:Name}`` then
fields ``{i:1}`` int, ``{s:"text"}`` string, ``{b:1}`` byte, ``{b:true}`` bool,
``{u:2}`` short, ``{l:3}`` long, ``{d:1.5}`` double, ``{f:1.5}`` float (G-Earth's codes).
Names must be in the catalogue (``--packet``; a few
common chat packets are included by default with ids from a 2026-10 macOS build).

Exit code 0 = every intercept answered within the time limit and the process exited
after the socket closed.
"""

from __future__ import annotations

import argparse
import re
import shlex
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

# G-Earth -> extension
ON_DOUBLE_CLICK, INFO_REQUEST, PACKET_INTERCEPT, FLAGS_CHECK = 1, 2, 3, 4
CONNECTION_START, CONNECTION_END, INIT = 5, 6, 7
# extension -> G-Earth
EXTENSION_INFO, MANIPULATED_PACKET, REQUEST_FLAGS, SEND_MESSAGE = 1, 2, 3, 4
EXTENSION_CONSOLE_LOG = 98

DEFAULT_PACKETS = [
    "in:Chat=1536", "in:Shout=2737", "in:Whisper=1535", "in:FloodControl=1199",
    "in:RemainingMutePeriod=671", "out:Chat=2096", "out:Shout=980", "out:Whisper=1875",
]  # fmt: skip
SLOW_CALLBACK_S = 0.05


# --------------------------------------------------------------------------- framing


def frame(msg_type: int, payload: bytes = b"") -> bytes:
    return struct.pack(">iH", len(payload) + 2, msg_type) + payload


def s2(text: str, encoding: str = "utf-8") -> bytes:
    raw = text.encode(encoding)
    return struct.pack(">H", len(raw)) + raw


def s4(raw: bytes) -> bytes:
    return struct.pack(">i", len(raw)) + raw


class Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise ValueError("short message from the extension")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def int(self) -> int:
        return struct.unpack(">i", self.take(4))[0]

    def bool(self) -> bool:
        return self.take(1) != b"\x00"

    def str2(self) -> str:
        return self.take(struct.unpack(">H", self.take(2))[0]).decode("utf-8", "replace")

    def str4(self) -> bytes:
        return self.take(self.int())


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError
        buf += chunk
    return buf


def recv_frame(sock: socket.socket) -> tuple[int, bytes]:
    length = struct.unpack(">i", recv_exact(sock, 4))[0]
    body = recv_exact(sock, length)
    return struct.unpack(">H", body[:2])[0], body[2:]


# --------------------------------------------------------------------------- expressions

EXPR_HEAD = re.compile(r"^\{(in|out):([A-Za-z0-9_]+)\}")
EXPR_FIELD = re.compile(r'\{([isbBuldf]):("(?:[^"\\]|\\.)*"|[^}]*)\}')


def build_packet(expr: str, ids: dict[tuple[str, str], int]) -> tuple[str, str, bytes]:
    """``{out:Chat}{s:"hi"}{i:0}`` -> (direction, name, raw packet bytes)."""
    head = EXPR_HEAD.match(expr.strip())
    if not head:
        raise SystemExit(f"error: expression must start with {{in:Name}} or {{out:Name}}: {expr}")
    direction, name = head.groups()
    if (direction, name) not in ids:
        raise SystemExit(
            f"error: {direction}:{name} isn't in the catalogue; add --packet {direction}:{name}=ID"
        )
    payload = b""
    rest = expr.strip()[head.end() :]
    pos = 0
    for m in EXPR_FIELD.finditer(rest):
        if m.start() != pos:
            raise SystemExit(f"error: can't read {rest[pos : m.start()]!r} in {expr}")
        pos = m.end()
        kind, value = m.groups()
        if kind == "s":
            text = value[1:-1] if value.startswith('"') else value
            payload += s2(bytes(text, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8"))
        elif kind == "i":
            payload += struct.pack(">i", int(value))
        elif kind == "u":
            payload += struct.pack(">h", int(value))
        elif kind == "l":
            payload += struct.pack(">q", int(value))
        elif kind == "d":
            payload += struct.pack(">d", float(value))
        elif kind == "f":
            payload += struct.pack(">f", float(value))
        elif kind in ("b", "B") and value.lower() in ("true", "false"):
            payload += b"\x01" if value.lower() == "true" else b"\x00"
        elif kind in ("b", "B"):
            payload += struct.pack(">B", int(value) & 0xFF)
    if pos != len(rest):
        raise SystemExit(f"error: can't read {rest[pos:]!r} in {expr}")
    raw = struct.pack(">iH", len(payload) + 2, ids[(direction, name)]) + payload
    return direction, name, raw


# --------------------------------------------------------------------------- session


@dataclass
class Session:
    sock: socket.socket
    answers: dict[int, tuple[float, bytes]] = field(default_factory=dict)
    sent: list[tuple[bool, bytes]] = field(default_factory=list)
    console: list[str] = field(default_factory=list)
    info: dict | None = None
    closed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    got: threading.Condition = field(init=False)

    def __post_init__(self):
        self.got = threading.Condition(self.lock)

    def reader(self) -> None:
        try:
            while True:
                kind, body = recv_frame(self.sock)
                r = Reader(body)
                with self.got:
                    if kind == EXTENSION_INFO:
                        self.info = {
                            "title": r.str2(), "author": r.str2(), "version": r.str2(),
                            "description": r.str2(), "click_trigger": r.bool(),
                            "has_file": r.bool(), "file": r.str2(), "cookie": r.str2(),
                            "can_leave": r.bool(), "can_delete": r.bool(),
                        }  # fmt: skip
                    elif kind == MANIPULATED_PACKET:
                        text = r.str4().decode("latin-1")
                        blocked, index, _direction, packet = text.split("\t", 3)
                        self.answers[int(index)] = (time.monotonic(), (blocked == "1", packet))
                    elif kind == SEND_MESSAGE:
                        to_server = r.bool()
                        size = r.int()
                        self.sent.append((to_server, r.take(size)))
                    elif kind == EXTENSION_CONSOLE_LOG:
                        self.console.append(r.str2())
                    elif kind == REQUEST_FLAGS:
                        self.sock.sendall(frame(FLAGS_CHECK, struct.pack(">i", 0)))
                    else:
                        print(f"  (unhandled message type {kind} from the extension)")
                    self.got.notify_all()
        except (EOFError, OSError, ValueError):
            with self.got:
                self.closed = True
                self.got.notify_all()

    def wait_for(self, predicate, timeout: float) -> bool:
        with self.got:
            return self.got.wait_for(lambda: predicate() or self.closed, timeout) and predicate()


def catalogue(specs: list[str]) -> tuple[dict[tuple[str, str], int], bytes]:
    ids: dict[tuple[str, str], int] = {}
    entries = b""
    for spec in specs:
        m = re.fullmatch(r"(in|out):([A-Za-z0-9_]+)=(\d+)", spec.strip())
        if not m:
            raise SystemExit(f"error: --packet must look like out:Chat=2096, not {spec!r}")
        direction, name, header = m.group(1), m.group(2), int(m.group(3))
        ids[(direction, name)] = header
        entries += struct.pack(">i", header) + s2("NULL") + s2(name) + s2("NULL")
        entries += (b"\x01" if direction == "out" else b"\x00") + s2("FakeGEarth")
    return ids, struct.pack(">i", len(ids)) + entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=0, help="0 = any free port")
    ap.add_argument("--run", help="command to start the extension; {port} is filled in")
    ap.add_argument("--wait", action="store_true", help="just listen; start the extension yourself")
    ap.add_argument("--packet", action="append", default=[], help="catalogue entry in|out:Name=ID")
    ap.add_argument(
        "--intercept", action="append", default=[], help="packet expression to pass through the extension"
    )
    ap.add_argument("--double-click", action="store_true", help="also press the extension's ▶")
    ap.add_argument("--client-type", default="FLASH")
    ap.add_argument("--hotel-version", default="FAKE-20261018-000000000")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument(
        "--linger", type=float, default=2.0, help="seconds to collect sends after the last intercept"
    )
    args = ap.parse_args(argv)
    if not args.run and not args.wait:
        ap.error("give --run COMMAND or --wait")

    ids, catalogue_bytes = catalogue(DEFAULT_PACKETS + args.packet)
    planned = [build_packet(e, ids) for e in args.intercept]
    names = {v: k for k, v in ids.items()}

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(1)
    port = server.getsockname()[1]
    print(f"fake G-Earth listening on 127.0.0.1:{port}")
    proc = None
    if args.run:
        cmd = shlex.split(args.run.replace("{port}", str(port)))
        proc = subprocess.Popen(cmd)  # noqa: S603 - the user's own command
    server.settimeout(args.timeout if proc else None)
    try:
        sock, _ = server.accept()
    except TimeoutError:
        print("FAIL: the extension never connected")
        if proc:
            proc.kill()
        return 1
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    session = Session(sock)
    threading.Thread(target=session.reader, daemon=True).start()
    ok = True

    sock.sendall(frame(INFO_REQUEST))
    if not session.wait_for(lambda: session.info is not None, args.timeout):
        print("FAIL: no EXTENSION_INFO answer")
        return 1
    info = session.info
    print(
        f"extension: {info['title']} {info['version']} by {info['author']}"
        f" (file={info['file'] or '-'}, cookie={'yes' if info['cookie'] else 'no'},"
        f" ▶={info['click_trigger']})"
    )
    sock.sendall(frame(INIT, b"\x01"))  # True: wait for CONNECTION_START before start() returns
    start = s2("game-fake.habbo.com") + struct.pack(">i", 30001) + s2(args.hotel_version)
    start += s2("fake-client") + s2(args.client_type) + catalogue_bytes
    sock.sendall(frame(CONNECTION_START, start))
    time.sleep(0.3)
    if args.double_click:
        sock.sendall(frame(ON_DOUBLE_CLICK))

    for index, (direction, name, raw) in enumerate(planned, start=1):
        tag = "TOCLIENT" if direction == "in" else "TOSERVER"
        text = f"0\t{index}\t{tag}\t0".encode("latin-1") + raw
        sent_at = time.monotonic()
        sock.sendall(frame(PACKET_INTERCEPT, s4(text)))
        if not session.wait_for(lambda i=index: i in session.answers, args.timeout):
            print(f"FAIL: {direction}:{name} #{index} was never answered (callback stuck or crashed?)")
            ok = False
            break
        at, (blocked, packet) = session.answers[index]
        took = at - sent_at
        edited = packet[:1] == "1"
        body = packet[1:].encode("latin-1")
        changed = body != raw
        slow = (
            f"  SLOW ({took * 1000:.0f} ms): callbacks must only parse and queue"
            if took > SLOW_CALLBACK_S
            else ""
        )
        print(
            f"{direction}:{name} #{index}: {'BLOCKED' if blocked else 'passed'}"
            f"{', edited' if edited or changed else ''}, answered in {took * 1000:.1f} ms{slow}"
        )
        if changed:
            print(f"    new bytes: {body.hex(' ')}")

    time.sleep(args.linger)
    with session.lock:
        for to_server, raw in session.sent:
            header = struct.unpack(">H", raw[4:6])[0] if len(raw) >= 6 else -1
            label = names.get(header, ("?", f"id {header}"))
            print(
                f"extension sent {'to server' if to_server else 'to client'}: "
                f"{label[0]}:{label[1]} {raw[6:].hex(' ')}"
            )
        for line in session.console:
            print(f"console: {line}")

    sock.sendall(frame(CONNECTION_END))
    time.sleep(0.2)
    sock.close()
    server.close()
    if proc:
        try:
            proc.wait(timeout=args.timeout)
            print(f"extension exited with code {proc.returncode} after the socket closed")
        except subprocess.TimeoutExpired:
            print(
                "FAIL: the extension kept running after G-Earth closed the socket "
                "(the store requires it to exit)"
            )
            proc.kill()
            ok = False
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
