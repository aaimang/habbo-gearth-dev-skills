#!/usr/bin/env python3
"""Check every skill in skills/: frontmatter, links to bundled files, script self-tests.

Usage::

    python3 scripts/validate_skills.py            # all checks, offline
    python3 scripts/validate_skills.py --no-run   # skip running the self-tests

Exit code 0 when everything passes. Standard library only (Python 3.9+).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # agentskills.io: no leading/trailing/double hyphens
# Self-tests that need no network or secrets: (skill, script args, text expected in stdout)
SELFTESTS = [
    ("habbo-gearth", ["scripts/habbo_packets.py", "selftest"], "selftest OK"),
    ("habbo-gearth", ["scripts/validate_store_entry.py", "--selftest"], "selftest OK"),
    ("habbo-wired-api", ["scripts/furni_ids.py"], "furni_ids: ok"),
    ("habbo-wired-api", ["scripts/level_upper.py"], "level_upper: ok"),
]
JUNK = {".DS_Store", "__pycache__", ".ruff_cache", ".pytest_cache", "Thumbs.db"}
SECRET_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}"
    r"|X-Wired-(Read|Write)-Key:\s*[A-Za-z0-9]{16,})"
)


def frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    """Top-level keys of the YAML frontmatter (simple parser: key: value lines)."""
    if not text.startswith("---\n"):
        return {}, ["SKILL.md must start with '---' frontmatter"]
    end = text.find("\n---", 4)
    if end == -1:
        return {}, ["frontmatter isn't closed with '---'"]
    keys: dict[str, str] = {}
    errors = []
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            errors.append(f"frontmatter line isn't 'key: value': {line[:60]}")
            continue
        value = value.strip()
        if value and not value.startswith(("'", '"', "|", ">")) and ": " in value:
            errors.append(f"{key}: unquoted ': ' in the value breaks strict YAML")
        keys[key.strip()] = value.strip("'\"")
    return keys, errors


def metadata_problems(text: str) -> list[str]:
    """agentskills.io: ``metadata`` maps string keys to string values (quote numbers/dates)."""
    end = text.find("\n---", 4)
    block, inside, problems = text[4:end].splitlines(), False, []
    for line in block:
        if line.startswith("metadata:"):
            inside = True
            continue
        if inside and line and not line.startswith((" ", "\t")):
            inside = False
        if inside and line.strip():
            key, _, value = line.strip().partition(":")
            value = value.strip()
            if not value:
                problems.append(f"metadata.{key} must be a string, not a nested map")
            elif re.fullmatch(r"-?\d+(\.\d+)?|true|false|null|\d{4}-\d{2}-\d{2}", value):
                problems.append(f"metadata.{key}: quote {value!r} so it stays a string")
    return problems


def check_skill(path: Path, run: bool) -> list[str]:
    errors: list[str] = []
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        return [f"{path.name}: no SKILL.md"]
    text = skill_md.read_text("utf-8")
    keys, problems = frontmatter(text)
    errors += [f"{path.name}: {p}" for p in problems]
    for extra in sorted(set(keys) - ALLOWED_KEYS):
        errors.append(f"{path.name}: frontmatter key {extra!r} not allowed")
    name, desc = keys.get("name", ""), keys.get("description", "")
    if name != path.name:
        errors.append(f"{path.name}: name {name!r} must equal the folder name")
    if not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"{path.name}: name must be lowercase-hyphenated, <= 64 chars")
    if not desc or len(desc) > 1024 or "<" in desc or ">" in desc:
        errors.append(f"{path.name}: description must be 1-1024 chars without angle brackets")
    compat = keys.get("compatibility")
    if compat is not None and not 1 <= len(compat) <= 500:
        errors.append(f"{path.name}: compatibility must be 1-500 chars")
    errors += [f"{path.name}: {p}" for p in metadata_problems(text)]
    lines = text.count("\n")
    if lines > 500:
        errors.append(f"{path.name}: SKILL.md has {lines} lines (keep under 500)")

    # every bundled path mentioned in SKILL.md exists
    for ref in sorted(set(re.findall(r"`((?:references|scripts|assets)/[^`\s*]+?)`", text))):
        target = path / ref.split(" ")[0]
        if not target.exists():
            errors.append(f"{path.name}: SKILL.md mentions {ref}, which doesn't exist")

    for f in path.rglob("*"):
        if f.name in JUNK:
            errors.append(f"{path.name}: remove {f.relative_to(path)}")
        elif f.is_file() and f.suffix in {".md", ".py", ".ts", ".toml", ".json"}:
            if SECRET_RE.search(f.read_text("utf-8", errors="replace")):
                errors.append(f"{path.name}: possible secret in {f.relative_to(path)}")

    if run:
        for skill, args, expected in SELFTESTS:
            if skill != path.name:
                continue
            done = subprocess.run(  # noqa: S603 - fixed commands
                [sys.executable, *args], cwd=path, capture_output=True, text=True, timeout=120
            )
            if done.returncode != 0 or expected not in done.stdout:
                errors.append(f"{path.name}: {' '.join(args)} failed:\n{done.stdout}{done.stderr}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-run", action="store_true", help="don't run the script self-tests")
    args = ap.parse_args(argv)
    skills = sorted(p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith("."))
    errors: list[str] = []
    for skill in skills:
        found = check_skill(skill, run=not args.no_run)
        print(f"{'ok  ' if not found else 'FAIL'} {skill.name}")
        errors += found
    for e in errors:
        print(f"  - {e}")
    print(f"{len(skills)} skill(s), {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
