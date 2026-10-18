#!/usr/bin/env python3
"""Create a new G-Python extension project from the skill's template (stdlib only).

Usage::

    scaffold.py --title "Room Helper" --dest ~/code/room-helper \
        --description "Small helpers for my room" --author "yourname"

Produces a uv project (``pyproject.toml``, ``src/<package>/``, ``tests/``,
``scripts/install_gearth.py``, README, .gitignore) that passes ``uv run pytest`` and
``uv run ruff check`` as generated. Package and distribution names are derived from
the title unless given. Refuses to write into a non-empty folder.
"""

from __future__ import annotations

import argparse
import keyword
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "gpython-template"
RENAMES = {"gitignore.template": ".gitignore"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
TEXT_SUFFIXES = {".py", ".toml", ".md", ".txt", ".template", ".json", ".cfg", ""}


def derive(title: str) -> tuple[str, str]:
    words = re.findall(r"[A-Za-z0-9]+", title.lower())
    if not words:
        raise SystemExit("error: the title needs letters or digits")
    pkg = "_".join(words)
    if pkg[0].isdigit() or keyword.iskeyword(pkg):
        pkg = f"ext_{pkg}"
    return pkg, "-".join(words)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--title", required=True, help="shown in G-Earth; no '_' or '.' (store rule)")
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--description", default="A G-Earth extension.")
    ap.add_argument("--author", default="unknown")
    ap.add_argument("--package", help="Python package name (default: from the title)")
    ap.add_argument("--dist", help="distribution name (default: from the title)")
    args = ap.parse_args(argv)

    if len(args.title) > 40:
        raise SystemExit("error: keep the title to 40 characters (it is shown in G-Earth's list)")
    if re.search(r"[_.]", args.title) or len(args.title) <= 4:
        raise SystemExit(
            "error: title must be longer than 4 characters with no '_' or '.' "
            "(G-Earth splits folder names on '_'; the store forbids both)"
        )
    if any(c in args.description for c in '"\\'):
        raise SystemExit("error: keep quotes and backslashes out of the description")
    pkg, dist = derive(args.title)
    pkg, dist = args.package or pkg, args.dist or dist
    if not pkg.isidentifier():
        raise SystemExit(f"error: {pkg!r} isn't a valid Python package name")

    dest = args.dest.expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"error: {dest} isn't empty")

    values = {
        "__TITLE__": args.title,
        "__DESC__": args.description,
        "__AUTHOR__": args.author,
        "__PKG__": pkg,
        "__DIST__": dist,
    }

    def fill(text: str) -> str:
        for key, value in values.items():
            text = text.replace(key, value)
        return text

    written = 0
    for src in sorted(TEMPLATE.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts or src.name in SKIP_NAMES:
            continue
        rel = src.relative_to(TEMPLATE)
        parts = [RENAMES.get(p, fill(p)) for p in rel.parts]
        out = dest.joinpath(*parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in TEXT_SUFFIXES:
            out.write_text(fill(src.read_text("utf-8")), "utf-8")
        else:
            shutil.copy2(src, out)
        written += 1

    print(f"Created {dest} ({written} files): package {pkg}, project {dist}")
    print("Next:")
    print(f"  cd {dest}")
    print("  git init && uv sync && uv run pytest")
    print("  uv run python scripts/install_gearth.py --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
