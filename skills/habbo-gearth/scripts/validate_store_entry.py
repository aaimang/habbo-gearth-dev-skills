#!/usr/bin/env python3
"""Check a G-ExtensionStore submission folder before opening the PR (stdlib only).

Mirrors the store's own CI (``scripts/tests/extensions/*.test.js`` in
sirjonasxx/G-ExtensionStore, branch ``repo/1.5.3``, read 2026-10-18), plus a few
review rules from its README that CI doesn't check (no hardcoded header ids, source
must be a git repo, ``stable`` must be true in the first PR).

Usage::

    validate_store_entry.py "store/extensions/My Extension"
    validate_store_entry.py path/to/folder --first-submission
    validate_store_entry.py --selftest

Exit code 0 = no errors (warnings may still be printed).
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ALLOWED_FILES = {"extension.json", "extension.zip", "icon.png", "screenshot.png"}
CATEGORIES = {"Fun", "Games", "Trading", "Building", "Moderation", "Usability", "G-Earth Utilities", "Others"}
FRAMEWORK_LANGUAGES = {
    "Native": {"Java"},
    "G-Python": {"Python"},
    "Geode": {"C#", "Visual Basic"},
    "G-Node": {"Node.js", "ts-node"},
    "G-Rust": {"Rust"},
    "Xabbo": {"C#"},
    "GoEarth": {"Go"},
    "G-PHP": {"PHP"},
    "QX": {"C#"},
}
HOTELS = {".com.br", ".de", ".nl", ".es", ".fi", ".fr", ".it", ".com.tr", ".com"}
SYSTEMS = {"Linux", "Windows", "Mac"}
CLIENTS = {"Unity", "Flash", "Nitro", "Origins"}
DATE_FMT = "%d-%m-%Y %H:%M:%S"
VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")
URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)
# Header-id smells inside the zip: HPacket(1234, ...), intercept(..., 1234), {out:1234}
HEADER_ID_RES = [
    re.compile(rb"HPacket\(\s*\d{2,5}\s*[,)]"),
    re.compile(rb"intercept\([^)\n]*,\s*\d{2,5}\s*\)"),
    re.compile(rb"\{(?:in|out|l|h):\d{2,5}\}"),
]


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def check(folder: Path, first_submission: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    err, warn = errors.append, warnings.append

    if not folder.is_dir():
        return [f"{folder} is not a folder"], []
    names = {p.name for p in folder.iterdir()}
    for extra in sorted(names - ALLOWED_FILES):
        err(f"unexpected file {extra!r}: only {', '.join(sorted(ALLOWED_FILES))} are allowed")
    for required in ("extension.json", "extension.zip", "icon.png"):
        if required not in names:
            err(f"missing {required}")

    for img, (wmin, hmin, wmax, hmax) in {
        "icon.png": (20, 20, 80, 80),
        "screenshot.png": (128, 64, 960, 1200),
    }.items():
        path = folder / img
        if path.is_file():
            size = png_size(path)
            if size is None:
                err(f"{img} isn't a PNG")
            elif not (wmin <= size[0] <= wmax and hmin <= size[1] <= hmax):
                err(f"{img} is {size[0]}x{size[1]}; allowed {wmin}-{wmax} x {hmin}-{hmax} px")
            elif img == "icon.png" and size != (40, 40):
                warn(f"icon.png is {size[0]}x{size[1]}; it's shown at 40x40")

    meta_path = folder / "extension.json"
    if not meta_path.is_file():
        return errors, warnings
    try:
        e = json.loads(meta_path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return errors + [f"extension.json isn't valid JSON: {exc}"], warnings

    title = e.get("title")
    if not isinstance(title, str) or not re.fullmatch(r"[^_.]+", title) or len(title) <= 4:
        err("title must be a string longer than 4 characters with no '.' or '_'")
    elif title != folder.name:
        err(f"folder name {folder.name!r} must equal the title {title!r}")
    if not isinstance(e.get("description"), str):
        err("description must be a string")
    authors = e.get("authors") or []
    if not authors:
        err("at least one author is required")
    for a in authors:
        if not isinstance(a.get("name"), str):
            err("every author needs a name")
        if a.get("hotel") not in (None, "") and a["hotel"] not in HOTELS:
            err(f"author hotel {a['hotel']!r} must be one of {sorted(HOTELS)}")
    if not isinstance(e.get("version"), str) or not VERSION_RE.match(e["version"]):
        err("version may only contain digits and dots, e.g. 1.0.0")
    cats = e.get("categories") or []
    if not cats:
        err("at least one category is required")
    for c in cats:
        if c not in CATEGORIES:
            err(f"unknown category {c!r}; use {sorted(CATEGORIES)}")
    if not isinstance(e.get("source"), str) or not URL_RE.match(e["source"]):
        err("source must be the URL of the git repository")
    for opt in ("readme", "releases"):
        if e.get(opt) not in (None, "") and not URL_RE.match(str(e[opt])):
            err(f"{opt} must be a URL, empty or null")
    if not isinstance(e.get("stable"), bool):
        err("stable must be true or false")
    elif first_submission and not e["stable"]:
        err("stable must be true in the first PR")
    fw = e.get("framework") or {}
    if fw.get("name") not in FRAMEWORK_LANGUAGES:
        err(f"framework.name must be one of {sorted(FRAMEWORK_LANGUAGES)}")
    elif e.get("language") not in FRAMEWORK_LANGUAGES[fw["name"]]:
        err(f"language for {fw['name']} must be one of {sorted(FRAMEWORK_LANGUAGES[fw['name']])}")
    if not isinstance(fw.get("version"), str) or not VERSION_RE.match(fw.get("version", "")):
        warn("framework.version should be a version like 0.1.6 (the framework version you built with)")

    commands = e.get("commands") or {}
    if not isinstance(commands.get("default"), list):
        err("commands.default must be a list (the argv)")
    for key, cmd in commands.items():
        if key != "default" and key not in {s.lower() for s in SYSTEMS}:
            err(f"commands.{key}: only default, linux, windows, mac are allowed")
            continue
        joined = " ".join(cmd) if isinstance(cmd, list) else ""
        for ph in ("{cookie}", "{port}", "{filename}"):
            if ph not in joined:
                err(f"commands.{key} must contain {ph}")
        if isinstance(cmd, list) and cmd and cmd[0] == "python":
            warn(f"commands.{key} runs 'python': often missing on macOS; consider a mac command with python3")

    comp = e.get("compatibility") or {}
    systems, clients = comp.get("systems") or [], comp.get("clients") or []
    if not systems or any(s not in SYSTEMS for s in systems):
        err(f"compatibility.systems must be a non-empty subset of {sorted(SYSTEMS)}")
    if not clients or any(c not in CLIENTS for c in clients):
        err(f"compatibility.clients must be a non-empty subset of {sorted(CLIENTS)}")

    dates = {}
    for key in ("submissionDate", "updateDate"):
        try:
            dates[key] = datetime.strptime(str(e.get(key)), DATE_FMT)
            if dates[key] > datetime.now() + timedelta(days=1):
                err(f"{key} is in the future")
        except ValueError:
            err(f"{key} must look like 15-08-2021 01:16:35 (DD-MM-YYYY HH:MM:SS)")
    if len(dates) == 2 and dates["updateDate"] < dates["submissionDate"]:
        err("updateDate can't be before submissionDate")
    if not isinstance(e.get("isOutdated"), bool):
        err("isOutdated must be true or false")

    zpath = folder / "extension.zip"
    if zpath.is_file():
        try:
            with zipfile.ZipFile(zpath) as z:
                members = z.namelist()
                first = commands.get("default") or [None, None]
                target = next(
                    (a for a in first[1:] if isinstance(a, str) and "." in a and not a.startswith("{")), None
                )
                if target and not any(m == target or m.endswith("/" + target) for m in members):
                    warn(
                        f"commands.default refers to {target!r}, which isn't in extension.zip "
                        "(paths are relative to the unzipped folder)"
                    )
                for m in members:
                    if m.endswith((".py", ".js", ".ts", ".java", ".cs", ".go", ".rs", ".php")):
                        body = z.read(m)
                        for rx in HEADER_ID_RES:
                            hit = rx.search(body)
                            if hit:
                                warn(
                                    f"{m}: looks like a hardcoded header id ({hit.group(0)[:40]!r}); "
                                    "the store requires packet names"
                                )
                                break
                    if m.endswith((".env", "config.toml")) or "/.env" in m:
                        err(f"extension.zip contains {m!r}; never ship secrets or personal config")
        except zipfile.BadZipFile:
            err("extension.zip isn't a valid zip")
    return errors, warnings


def selftest() -> int:
    good = {
        "title": "Chat Helper",
        "description": "Helps with chat.",
        "authors": [{"name": "dev", "hotel": ".com"}],
        "version": "1.0.0",
        "categories": ["Usability"],
        "source": "https://github.com/example/chat-helper",
        "readme": None,
        "releases": "",
        "stable": True,
        "framework": {"name": "G-Python", "version": "0.1.6"},
        "language": "Python",
        "commands": {"default": ["python", "main.py", "-c", "{cookie}", "-p", "{port}", "-f", "{filename}"]},
        "compatibility": {"systems": ["Windows", "Mac"], "clients": ["Flash"]},
        "submissionDate": "18-10-2026 10:00:00",
        "updateDate": "18-10-2026 10:00:00",
        "isOutdated": False,
    }
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 40, 40) + b"\x08\x06\x00\x00\x00"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "Chat Helper"
        folder.mkdir()
        (folder / "extension.json").write_text(json.dumps(good))
        (folder / "icon.png").write_bytes(png)
        with zipfile.ZipFile(folder / "extension.zip", "w") as z:
            z.writestr("main.py", 'HPacket("Chat", "hi", 0, -1)\n')
        errors, warnings = check(folder, first_submission=True)
        assert not errors, errors
        bad = dict(
            good,
            title="My_Ext",
            version="v1",
            categories=["Bots"],
            stable=False,
            language="Java",
            commands={"default": ["python", "main.py"]},
        )
        (folder / "extension.json").write_text(json.dumps(bad))
        (folder / "notes.txt").write_text("x")
        with zipfile.ZipFile(folder / "extension.zip", "w") as z:
            z.writestr("main.py", "ext.send_to_server(HPacket(2096, 'hi'))\n")
            z.writestr(".env", "KEY=x")
        errors, warnings = check(folder, first_submission=True)
        text = "\n".join(errors + warnings)
        for needle in (
            "title",
            "version",
            "category",
            "stable",
            "language",
            "{cookie}",
            "notes.txt",
            "header id",
            ".env",
        ):
            assert needle in text, (needle, text)
    print("selftest OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", nargs="?", type=Path)
    ap.add_argument("--first-submission", action="store_true", help="also require stable: true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.folder is None:
        ap.error("folder is required")
    errors, warnings = check(args.folder, args.first_submission)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
