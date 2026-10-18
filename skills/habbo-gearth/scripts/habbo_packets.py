#!/usr/bin/env python3
"""Look up and decode Habbo packets (stdlib only, Python 3.9+).

Data comes from HabboPackets (https://laande.github.io/HabboPackets/, generated from
G-Rust's parsers) and, for header ids, from Sulek (https://api.sulek.dev), which is
what G-Earth itself uses for Flash/AIR names. Both are cached for 7 days in
``$XDG_CACHE_HOME/habbo-gearth`` (default ``~/.cache/habbo-gearth``) so lookups work
offline after the first run.

Layouts are the DOCUMENTED ones. The live AIR client sometimes sends extra fields
(see references/bugs-and-workarounds.md), so trailing bytes after a decode are a clue,
not an error.

Usage::

    habbo_packets.py show Chat                 # both directions, fields expanded
    habbo_packets.py show Users --dir in
    habbo_packets.py search avatar             # names containing "avatar"
    habbo_packets.py template UserUpdateMessageData
    habbo_packets.py id Chat --build MAC63-202610131318-613990583
    habbo_packets.py decode --packet Chat --dir in --hex "00 00 00 01 00 02 68 69 ..."
    habbo_packets.py decode --layout "i s i" --file logs/bad-packets/Users-x.hex
    habbo_packets.py selftest                  # offline checks of the decoder

Layout notation (HabboPackets): s string (u16 length + UTF-8), S string (u32 length),
c byte, h short, i int, d long, b bool, f float, g double, ``i[ ... ]`` counted list,
``#N[ ... ]`` fixed array, ``<Name>`` shared structure, ``x?`` optional,
``( a | b )`` one of several variants, ``·`` an empty variant. Note: G-Python's
``HPacket.read("...")`` uses DIFFERENT letters (b byte, B bool, u short, l long).
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HABBOPACKETS = "https://laande.github.io/HabboPackets/api/{name}.json"
SULEK = "https://api.sulek.dev/releases/{build}/messages"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "habbo-gearth"
CACHE_TTL_S = 7 * 24 * 3600
TIMEOUT_S = 15
DIRS = {"in": "in", "out": "out", "incoming": "in", "outgoing": "out", "toclient": "in", "toserver": "out"}
MAX_LIST = 100_000  # a count above this is treated as a misread


# --------------------------------------------------------------------------- data


def _fetch_json(url: str, cache_name: str, refresh: bool = False) -> Any:
    """Download JSON with a 7-day file cache; fall back to a stale cache offline."""
    path = CACHE_DIR / cache_name
    fresh = path.is_file() and time.time() - path.stat().st_mtime < CACHE_TTL_S
    if fresh and not refresh:
        return json.loads(path.read_text("utf-8"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "habbo-gearth-skill/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https URLs
            text = resp.read().decode("utf-8")
        data = json.loads(text, strict=False)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        if path.is_file():
            print(f"warning: {url} failed ({exc}); using cached copy", file=sys.stderr)
            return json.loads(path.read_text("utf-8"))
        raise SystemExit(f"error: couldn't download {url}: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), "utf-8")
    return data


def load(name: str, refresh: bool = False) -> Any:
    """One HabboPackets file: ``packets``, ``fields`` or ``templates``."""
    return _fetch_json(HABBOPACKETS.format(name=name), f"habbopackets-{name}.json", refresh)


def templates_by_name(refresh: bool = False) -> dict[str, dict]:
    return {t["name"]: t for t in load("templates", refresh)}


def norm_dir(value: str | None) -> list[str]:
    if value is None:
        return ["in", "out"]
    key = value.lower().replace("_", "").replace("-", "")
    if key not in DIRS:
        raise SystemExit(f"error: direction must be in or out, not {value!r}")
    return [DIRS[key]]


# --------------------------------------------------------------------------- show


def describe(node: dict, templates: dict[str, dict], depth: int, indent: int, seen: tuple) -> Iterator[str]:
    """Human-readable lines for one field node of fields.json/templates.json."""
    pad = "  " * indent
    name, kind = node.get("name", "?"), node.get("kind")
    if kind == "primitive":
        typ = node.get("type", "")
        hint = {
            "LegacyId": " (int on Flash/AIR, long on Unity)",
            "LegacyDouble": " (a decimal number sent as a string)",
            "LegacyStringId": " (an id sent as a string)",
        }.get(typ, "")
        yield f"{pad}{name}: {node['token']} {typ}{hint}"
    elif kind in ("list", "array"):
        size = f"count {node['count']}" if kind == "list" else f"exactly {node['size']}"
        yield f"{pad}{name}: list ({size}) of"
        yield from describe(node["of"], templates, depth, indent + 1, seen)
    elif kind == "map":
        yield f"{pad}{name}: map (count i) of key, value"
        yield from describe({**node["key"], "name": "key"}, templates, depth, indent + 1, seen)
        yield from describe({**node["value"], "name": "value"}, templates, depth, indent + 1, seen)
    elif kind == "optional":
        yield f"{pad}{name}: optional (may be absent at the end of the packet)"
        yield from describe({**node["of"], "name": name}, templates, depth, indent + 1, seen)
    elif kind == "tuple":
        yield f"{pad}{name}: tuple {node.get('layout', '')}"
        for item in node.get("items", []):
            yield from describe(item, templates, depth, indent + 1, seen)
    elif kind == "template":
        ref = node["ref"]
        tpl = templates.get(ref)
        if tpl is None or depth <= 0 or ref in seen:
            yield f"{pad}{name}: <{ref}>"
            return
        yield from describe_template(tpl, templates, depth - 1, indent, seen + (ref,), label=name)
    else:
        yield f"{pad}{name}: {kind} {node.get('layout', '')}"


def describe_template(
    tpl: dict, templates: dict[str, dict], depth: int, indent: int, seen: tuple, label: str | None = None
) -> Iterator[str]:
    pad = "  " * indent
    head = f"{label}: " if label else ""
    est = "  [layout is an estimate: custom parser in G-Rust]" if tpl.get("layoutIsEstimate") else ""
    if tpl.get("kind") == "enum":
        yield f"{pad}{head}<{tpl['name']}> one of:{est}"
        for v in tpl.get("variants", []):
            yield f"{pad}  - {v['name']}: {v.get('layout') or '(empty)'}"
            for f in v.get("fields", []):
                yield from describe(f, templates, depth, indent + 2, seen)
    else:
        yield f"{pad}{head}<{tpl['name']}> {tpl.get('layout', '')}{est}"
        for f in tpl.get("fields", []):
            yield from describe(f, templates, depth, indent + 1, seen)
    if tpl.get("note"):
        yield f"{pad}  note: {tpl['note']}"


def cmd_show(args: argparse.Namespace) -> int:
    packets, fields = load("packets", args.refresh), load("fields", args.refresh)
    templates = templates_by_name(args.refresh)
    found = False
    for d in norm_dir(args.dir):
        entry = packets.get(d, {}).get(args.name)
        if entry is None:
            continue
        found = True
        detail = fields.get(d, {}).get(args.name, {})
        arrow = "server -> client (TO_CLIENT)" if d == "in" else "client -> server (TO_SERVER)"
        print(f"{args.name}  [{d}: {arrow}]")
        print(f"  layout: {entry.get('layout') or '(empty)'}")
        if entry.get("custom") or detail.get("layoutIsEstimate"):
            print("  note: custom parser in G-Rust; layout is an estimate, confirm with a capture")
        if detail.get("note"):
            print(f"  note: {detail['note']}")
        for f in detail.get("fields", []):
            for line in describe(f, templates, args.depth, 2, ()):
                print(line)
        print()
    if not found:
        close = [n for d in norm_dir(args.dir) for n in packets.get(d, {}) if args.name.lower() in n.lower()]
        print(
            f"{args.name}: not in HabboPackets."
            + (f" Did you mean: {', '.join(sorted(set(close))[:12])}" if close else "")
        )
        return 1
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    packets = load("packets", args.refresh)
    hits = 0
    for d in norm_dir(args.dir):
        for name, entry in sorted(packets.get(d, {}).items()):
            if args.text.lower() in name.lower():
                hits += 1
                print(f"{d:3}  {name:40}  {entry.get('layout') or '(empty)'}")
    if args.templates:
        for name, tpl in sorted(templates_by_name(args.refresh).items()):
            if args.text.lower() in name.lower():
                hits += 1
                print(f"tpl  {name:40}  {tpl.get('layout') or tpl.get('kind')}")
    return 0 if hits else 1


def cmd_template(args: argparse.Namespace) -> int:
    templates = templates_by_name(args.refresh)
    tpl = templates.get(args.name)
    if tpl is None:
        print(f"{args.name}: no such structure", file=sys.stderr)
        return 1
    for line in describe_template(tpl, templates, args.depth, 0, (args.name,)):
        print(line)
    return 0


# --------------------------------------------------------------------------- ids (Sulek)

SUFFIXES = ("", "MessageEvent", "MessageComposer", "Event", "Composer", "Message")


def cmd_id(args: argparse.Namespace) -> int:
    data = _fetch_json(SULEK.format(build=args.build), f"sulek-{args.build}.json", args.refresh)
    messages = data.get("messages", data)
    want = {d: ("incoming" if d == "in" else "outgoing") for d in norm_dir(args.dir)}
    ok = False
    for d, key in want.items():
        by_name = {m["name"]: m for m in messages.get(key, [])}
        for suffix in SUFFIXES:
            m = by_name.get(args.name + suffix)
            if m:
                ok = True
                sure = "" if m.get("confident", True) else "  (Sulek isn't confident about this match)"
                print(f"{d:3}  {args.name:30} id {m['id']:5}  Sulek name {m['name']}{sure}")
                break
    if not ok:
        print(f"{args.name}: not in Sulek's list for {args.build}", file=sys.stderr)
        return 1
    print("Ids change with every client build and differ per OS: use names in code.")
    return 0


# --------------------------------------------------------------------------- layout parser

TOKENS = {
    "s": ("string", None),
    "S": ("longstring", None),
    "c": ("byte", 1),
    "h": ("short", 2),
    "i": ("int", 4),
    "d": ("long", 8),
    "b": ("bool", 1),
    "f": ("float", 4),
    "g": ("double", 8),
}


@dataclass
class Node:
    kind: str  # prim | seq | list | array | alt | opt | ref | empty
    token: str = ""
    count: str = "i"
    size: int = 0
    ref: str = ""
    items: list[Node] = field(default_factory=list)


class LayoutError(ValueError):
    pass


def parse_layout(text: str) -> Node:
    """Parse HabboPackets notation into a tree."""
    pos = 0
    text = text.strip()

    def skip() -> None:
        nonlocal pos
        while pos < len(text) and text[pos] in " \t,":
            pos += 1

    def seq(stops: str) -> Node:
        nonlocal pos
        items: list[Node] = []
        while True:
            skip()
            if pos >= len(text) or text[pos] in stops:
                return Node("seq", items=items)
            items.append(postfix(atom()))

    def alt(stops: str) -> Node:
        nonlocal pos
        options = [seq(stops + "|")]
        while pos < len(text) and text[pos] == "|":
            pos += 1
            options.append(seq(stops + "|"))
        return options[0] if len(options) == 1 else Node("alt", items=options)

    def postfix(node: Node) -> Node:
        nonlocal pos
        if pos < len(text) and text[pos] == "?":
            pos += 1
            return Node("opt", items=[node])
        return node

    def expect(ch: str) -> None:
        nonlocal pos
        skip()
        if pos >= len(text) or text[pos] != ch:
            raise LayoutError(f"expected {ch!r} at {pos} in {text!r}")
        pos += 1

    def atom() -> Node:
        nonlocal pos
        ch = text[pos]
        if ch == "·":
            pos += 1
            return Node("empty")
        if ch == "(":
            pos += 1
            inner = alt(")")
            expect(")")
            return inner
        if ch == "<":
            end = text.index(">", pos)
            name = text[pos + 1 : end]
            pos = end + 1
            return Node("ref", ref=name)
        if ch == "#":
            pos += 1
            start = pos
            while pos < len(text) and text[pos].isdigit():
                pos += 1
            size = int(text[start:pos])
            expect("[")
            inner = alt("]")
            expect("]")
            return Node("array", size=size, items=[inner])
        if ch in TOKENS:
            pos += 1
            if pos < len(text) and text[pos] == "[":
                pos += 1
                inner = alt("]")
                expect("]")
                return Node("list", count=ch, items=[inner])
            return Node("prim", token=ch)
        raise LayoutError(f"unknown token {ch!r} at {pos} in {text!r}")

    tree = alt("")
    if pos != len(text):
        raise LayoutError(f"unexpected {text[pos]!r} at {pos} in {text!r}")
    return tree


# --------------------------------------------------------------------------- decoder


class Decoder:
    """Backtracking decoder: tries variants in order, greedy per list element."""

    def __init__(self, data: bytes, templates: dict[str, dict] | None = None):
        self.data = data
        self.templates = templates or {}
        self.furthest = 0
        self.furthest_why = ""
        self._cache: dict[str, Node] = {}

    def _fail(self, pos: int, why: str) -> None:
        if pos >= self.furthest:
            self.furthest, self.furthest_why = pos, why

    def prim(self, token: str, pos: int) -> tuple[int, Any] | None:
        d = self.data
        if token in ("s", "S"):
            head = 2 if token == "s" else 4
            if pos + head > len(d):
                return self._fail(pos, f"no room for a {token} length")
            n = int.from_bytes(d[pos : pos + head], "big")
            if pos + head + n > len(d):
                return self._fail(pos, f"string length {n} runs past the end")
            raw = d[pos + head : pos + head + n]
            return pos + head + n, raw.decode("utf-8", errors="replace")
        _, size = TOKENS[token]
        if pos + size > len(d):
            return self._fail(pos, f"no room for {TOKENS[token][0]}")
        chunk = d[pos : pos + size]
        if token == "b":
            if chunk[0] > 1:
                return self._fail(pos, f"bool byte {chunk[0]} isn't 0 or 1")
            return pos + 1, bool(chunk[0])
        fmt = {"c": ">b", "h": ">h", "i": ">i", "d": ">q", "f": ">f", "g": ">d"}[token]
        return pos + size, struct.unpack(fmt, chunk)[0]

    def ref(self, name: str) -> Node:
        if name not in self._cache:
            tpl = self.templates.get(name)
            if tpl is None:
                raise LayoutError(f"unknown structure <{name}> (load templates or inline it)")
            if tpl.get("kind") == "enum":
                layouts = [v.get("layout") or "·" for v in tpl.get("variants", [])]
                text = "(" + " | ".join(layouts) + ")"
                prefix = tpl.get("sharedPrefix")
                if prefix:
                    text = f"{prefix} {text}"
            else:
                text = tpl.get("layout") or ""
            self._cache[name] = parse_layout(text) if text else Node("seq")
        return self._cache[name]

    def run(self, node: Node, pos: int) -> Iterator[tuple[int, Any]]:
        k = node.kind
        if k == "empty":
            yield pos, None
        elif k == "prim":
            r = self.prim(node.token, pos)
            if r:
                yield r
        elif k == "ref":
            for p, v in self.run(self.ref(node.ref), pos):
                yield p, {node.ref: v}
        elif k == "opt":
            got = False
            for r in self.run(node.items[0], pos):
                got = True
                yield r
            if not got or pos >= len(self.data):
                yield pos, None
        elif k == "alt":
            for i, option in enumerate(node.items):
                single = option.kind == "seq" and len(option.items) == 1
                for p, v in self.run(option, pos):
                    yield p, {f"variant {i}": v[0] if single else v}
        elif k == "seq":
            yield from self._seq(node.items, 0, pos, [])
        elif k in ("list", "array"):
            if k == "list":
                r = self.prim(node.count, pos)
                if not r:
                    return
                pos, n = r
                if not 0 <= n <= MAX_LIST or n > len(self.data) - pos + 1:
                    return self._fail(pos, f"list count {n} is implausible")
            else:
                n = node.size
            values = []
            elem = node.items[0]
            single = elem.kind == "seq" and len(elem.items) == 1
            for i in range(n):  # greedy: first decode of each element wins
                nxt = next(iter(self.run(elem, pos)), None)
                if nxt is None:
                    self._fail(pos, f"element {i} of {n} didn't decode")
                    return
                pos, v = nxt
                values.append(v[0] if single else v)
            yield pos, values

    def _seq(self, items: list[Node], i: int, pos: int, acc: list) -> Iterator[tuple[int, Any]]:
        if i == len(items):
            yield pos, list(acc)
            return
        for p, v in self.run(items[i], pos):
            yield from self._seq(items, i + 1, p, acc + [v])

    def decode(self, node: Node, start: int) -> tuple[Any, int] | None:
        """Best decode: prefer one that uses every byte, else the longest."""
        best = None
        for count, (p, v) in enumerate(self.run(node, start)):
            if p == len(self.data):
                return v, p
            if best is None or p > best[1]:
                best = (v, p)
            if count > 5000:
                break
        return best


def read_hex(args: argparse.Namespace) -> bytes:
    if args.file:
        text = Path(args.file).read_text("utf-8")
    elif args.hex == "-":
        text = sys.stdin.read()
    else:
        text = args.hex or ""
    lines = [ln.split("|")[0] for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    cleaned = "".join(lines).replace(" ", "").replace(":", "").replace("0x", "")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise SystemExit(f"error: not hex: {exc}") from exc


def has_header(data: bytes) -> bool:
    return len(data) >= 6 and int.from_bytes(data[:4], "big") == len(data) - 4


def render(value: Any, indent: int = 0) -> Iterator[str]:
    pad = "  " * indent
    if isinstance(value, list):
        for i, v in enumerate(value):
            if isinstance(v, (list, dict)):
                yield f"{pad}[{i}]"
                yield from render(v, indent + 1)
            else:
                yield f"{pad}[{i}] {v!r}"
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (list, dict)):
                yield f"{pad}{k}:"
                yield from render(v, indent + 1)
            else:
                yield f"{pad}{k}: {v!r}"
    else:
        yield f"{pad}{value!r}"


def cmd_decode(args: argparse.Namespace) -> int:
    data = read_hex(args)
    templates: dict[str, dict] = {}
    if args.packet:
        dirs = norm_dir(args.dir or "in")
        layout = load("packets", args.refresh).get(dirs[0], {}).get(args.packet, {}).get("layout")
        if layout is None:
            raise SystemExit(f"error: {args.packet} ({dirs[0]}) isn't in HabboPackets")
    elif args.layout is not None:
        layout = args.layout
    else:
        raise SystemExit("error: give --packet NAME or --layout TEXT")
    if "<" in layout and not args.no_templates:
        templates = templates_by_name(args.refresh)
    start = 6 if (args.header == "yes" or (args.header == "auto" and has_header(data))) else 0
    if start:
        print(f"header: length {int.from_bytes(data[:4], 'big')}, id {int.from_bytes(data[4:6], 'big')}")
    print(f"layout: {layout}")
    dec = Decoder(data, templates)
    result = dec.decode(parse_layout(layout), start)
    if result is None:
        print(f"FAILED at byte {dec.furthest}: {dec.furthest_why}")
        print(f"bytes there: {data[dec.furthest : dec.furthest + 32].hex(' ')}")
        return 1
    value, end = result
    for line in render(value):
        print(line)
    left = len(data) - end
    if left:
        print(f"\n{left} byte(s) left over at {end}: {data[end : end + 48].hex(' ')}")
        print("The live client may send fields the documented layout lacks (compare a capture).")
        return 2
    print("\nOK: every byte decoded.")
    return 0


# --------------------------------------------------------------------------- selftest


def _pkt(header: int, payload: bytes) -> bytes:
    return (len(payload) + 2).to_bytes(4, "big") + header.to_bytes(2, "big") + payload


def _s(text: str) -> bytes:
    raw = text.encode("utf-8")
    return len(raw).to_bytes(2, "big") + raw


def _i(n: int) -> bytes:
    return n.to_bytes(4, "big", signed=True)


def selftest() -> int:
    chat = _pkt(1536, _i(7) + _s("héllo 👋") + _i(0) + _i(2) + _i(1) + _s("a") + _s("b") + b"\x01" + _i(-1))
    assert has_header(chat)
    v, end = Decoder(chat).decode(parse_layout("i s i i i[ssb] i"), 6)
    assert end == len(chat) and v[1] == "héllo 👋" and v[4] == [["a", "b", True]] and v[5] == -1, v
    # one extra trailing int: decodes, with 4 bytes left over
    v, end = Decoder(chat + _i(-1)).decode(parse_layout("i s i i i[ssb] i"), 6)
    assert len(chat) + 4 - end == 4
    # variants: picks the one that uses every byte
    v, end = Decoder(_i(2) + _s("x")).decode(parse_layout("i (i | s)"), 0)
    assert v == [2, {"variant 1": "x"}], v
    # optional tail, fixed array, empty variant, refs
    tpl = {"P": {"name": "P", "kind": "object", "layout": "i i"}}
    v, end = Decoder(_i(1) + _i(2) + b"\x01", tpl).decode(parse_layout("<P> b?"), 0)
    assert end == 9 and v == [{"P": [1, 2]}, True], v
    v, end = Decoder(_i(1) + _i(2), tpl).decode(parse_layout("<P> b?"), 0)
    assert end == 8 and v == [{"P": [1, 2]}, None], v
    v, end = Decoder(_s("a") + _s("b")).decode(parse_layout("#2[s]"), 0)
    assert v == [["a", "b"]], v
    v, end = Decoder(b"").decode(parse_layout("(· | i)"), 0)
    assert end == 0
    # truncated string fails cleanly
    dec = Decoder(_i(1) + b"\x00\x09ab")
    assert dec.decode(parse_layout("i s"), 0) == ([1], 4) or dec.furthest == 4
    for bad in ("i[", "q", "(i"):
        try:
            parse_layout(bad)
        except (LayoutError, ValueError, IndexError):
            pass
        else:
            raise AssertionError(f"accepted bad layout {bad!r}")
    print("selftest OK")
    return 0


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="re-download instead of using the cache")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="layout and fields of one packet")
    p.add_argument("name")
    p.add_argument("--dir", help="in (server->client) or out (client->server); default both")
    p.add_argument("--depth", type=int, default=2, help="how deep to expand <Structures>")

    p = sub.add_parser("search", help="packets whose name contains TEXT")
    p.add_argument("text")
    p.add_argument("--dir")
    p.add_argument("--templates", action="store_true", help="also search shared structures")

    p = sub.add_parser("template", help="one shared structure")
    p.add_argument("name")
    p.add_argument("--depth", type=int, default=2)

    p = sub.add_parser("id", help="header id for a client build (from Sulek)")
    p.add_argument("name")
    p.add_argument("--build", required=True, help="hotel version from G-Earth, e.g. MAC63-2026...")
    p.add_argument("--dir")

    p = sub.add_parser("decode", help="decode hex bytes against a layout")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--hex", help="hex string, or - for stdin")
    src.add_argument("--file", help="a .hex dump (# comment lines are skipped)")
    p.add_argument("--packet", help="take the layout from HabboPackets")
    p.add_argument("--dir", help="direction for --packet (default in)")
    p.add_argument("--layout", help="layout in HabboPackets notation")
    p.add_argument(
        "--header",
        choices=("auto", "yes", "no"),
        default="auto",
        help="whether the bytes start with length+id (auto-detected)",
    )
    p.add_argument("--no-templates", action="store_true")

    sub.add_parser("selftest", help="offline checks of the decoder")

    args = ap.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    return {
        "show": cmd_show,
        "search": cmd_search,
        "template": cmd_template,
        "id": cmd_id,
        "decode": cmd_decode,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
