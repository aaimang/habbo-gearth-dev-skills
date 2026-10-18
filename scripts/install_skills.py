#!/usr/bin/env python3
"""Install the skills for your coding agents by linking (or copying) them (stdlib only).

Agent Skills (agentskills.io) is a shared format; agents differ only in where they look:

    agents   ~/.agents/skills   Codex, Gemini CLI, Cursor (the cross-agent folder)
    claude   ~/.claude/skills   Claude Code (Cursor reads it too)
    gemini   ~/.gemini/skills   Gemini CLI's own folder (it also reads ~/.agents/skills)
    cursor   ~/.cursor/skills   Cursor's own folder (it also reads ~/.agents/skills)

The default, ``agents`` + ``claude``, covers all four. Symlinks mean ``git pull`` updates
every agent at once; use ``--copy`` where symlinks aren't allowed (Windows without
Developer Mode). For one project only, use ``--dest <project>/.agents/skills``.

Usage::

    python3 scripts/install_skills.py                  # ~/.agents/skills + ~/.claude/skills
    python3 scripts/install_skills.py --target agents  # only the cross-agent folder
    python3 scripts/install_skills.py --dest ./my-project/.agents/skills
    python3 scripts/install_skills.py --copy           # copy instead of symlink
    python3 scripts/install_skills.py --dry-run
    python3 scripts/install_skills.py --uninstall

Existing folders with the same name are left alone unless they are links into this repo
(or ``--force`` is given).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
TARGETS = {
    "agents": "~/.agents/skills",
    "claude": "~/.claude/skills",
    "gemini": "~/.gemini/skills",
    "cursor": "~/.cursor/skills",
}
DEFAULT_TARGETS = ("agents", "claude")


def ours(path: Path) -> bool:
    """Whether ``path`` is a link into this repo's skills folder."""
    try:
        return path.is_symlink() and path.resolve().parent == SKILLS.resolve()
    except OSError:
        return False


def install_one(skill: Path, dest_dir: Path, copy: bool, force: bool, dry: bool) -> str:
    target = dest_dir / skill.name
    if target.exists() or target.is_symlink():
        if ours(target) and not copy:
            return f"ok       {target} (already linked)"
        if not (force or ours(target)):
            return f"skipped  {target} exists and isn't from this repo (use --force)"
        if not dry:
            if target.is_symlink() or target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
    if not dry:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copytree(skill, target, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        else:
            target.symlink_to(skill, target_is_directory=True)
    verb = ("would copy" if dry else "copied") if copy else ("would link" if dry else "linked")
    return f"{verb:8} {target} -> {skill}"


def uninstall_one(skill: Path, dest_dir: Path, force: bool, dry: bool) -> str | None:
    target = dest_dir / skill.name
    if not (target.exists() or target.is_symlink()):
        return None
    if not (ours(target) or force):
        return f"skipped  {target} isn't a link into this repo (use --force)"
    if not dry:
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    return f"{'would remove' if dry else 'removed':8} {target}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", action="append", choices=sorted(TARGETS), help="repeatable")
    ap.add_argument("--dest", action="append", type=Path, help="any skills folder (repeatable)")
    ap.add_argument("--skill", action="append", help="only these skills (default: all)")
    ap.add_argument("--copy", action="store_true", help="copy instead of symlink")
    ap.add_argument("--force", action="store_true", help="replace folders not made by this script")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    skills = sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())
    if args.skill:
        unknown = set(args.skill) - {s.name for s in skills}
        if unknown:
            ap.error(f"unknown skill(s): {', '.join(sorted(unknown))}")
        skills = [s for s in skills if s.name in args.skill]
    dests = [Path(TARGETS[t]).expanduser() for t in (args.target or [])]
    dests += [d.expanduser().resolve() for d in (args.dest or [])]
    if not dests:
        dests = [Path(TARGETS[t]).expanduser() for t in DEFAULT_TARGETS]

    for dest in dests:
        for skill in skills:
            if args.uninstall:
                line = uninstall_one(skill, dest, args.force, args.dry_run)
            else:
                line = install_one(skill, dest, args.copy, args.force, args.dry_run)
            if line:
                print(line)
    if not args.uninstall and not args.dry_run:
        print("Restart your agent (or start a new session) so it picks the skills up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
