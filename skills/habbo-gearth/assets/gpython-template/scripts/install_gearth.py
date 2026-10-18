"""Register this project in G-Earth's Extensions list (macOS, Windows, Linux).

Writes ``<G-Earth data>/Extensions/__TITLE___<version>/command.txt``: the JSON argv
G-Earth runs, with ``{cookie}``, ``{port}`` and ``{filename}`` filled in at launch. It
points at this project's own virtualenv, so nothing is installed globally.

Where ``<G-Earth data>`` is (``--gearth-dir`` or ``GEARTH_DIR`` always win):

* macOS: ``~/Library/Application Support/G-Earth`` (the app's launcher sets
  ``-Dgearth.data.dir`` to this).
* Windows / Linux: the folder holding ``G-Earth.exe`` / ``G-Earth.jar``, wherever it was
  unzipped. Pass it with ``--gearth-dir``.

Usage::

    uv run python scripts/install_gearth.py                 # install / update
    uv run python scripts/install_gearth.py --gearth-dir "C:/Tools/G-Earth"
    uv run python scripts/install_gearth.py --dry-run       # show, change nothing
    uv run python scripts/install_gearth.py --uninstall

Then restart G-Earth AND the Habbo client.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from __PKG__ import __version__  # noqa: E402

# G-Earth folder names are <Title>_<version>
FOLDER_PREFIX = "__TITLE___"
MAC_DIR = Path("~/Library/Application Support/G-Earth").expanduser()
DS_STORE = ".DS_Store"


def gearth_dir(given: Path | None) -> Path | None:
    """The G-Earth data folder, or ``None`` if it can't be decided."""
    if given is None and os.environ.get("GEARTH_DIR"):
        given = Path(os.environ["GEARTH_DIR"])
    if given is not None:
        given = given.expanduser().resolve()
        return given.parent if given.is_file() else given
    if sys.platform == "darwin":
        return MAC_DIR
    return None


def venv_python() -> Path:
    """The project's virtualenv Python, as uv lays it out on this OS."""
    if sys.platform == "win32":
        return PROJECT / ".venv" / "Scripts" / "python.exe"
    return PROJECT / ".venv" / "bin" / "python"


def guard_ds_store(extensions: Path, dry_run: bool) -> None:
    """macOS: G-Earth tries to start every entry in Extensions/, and a ``.DS_Store``
    FILE (Finder writes one whenever the folder is viewed) crashes it before its window
    opens. Remove the file and leave an empty FOLDER of that name, which Finder can't
    overwrite and G-Earth skips."""
    path = extensions / DS_STORE
    if path.is_file():
        verb = "would remove" if dry_run else "removing"
        print(f"{verb} {path} (it stops G-Earth's window opening)")
        if not dry_run:
            path.unlink(missing_ok=True)
    if sys.platform == "darwin" and not path.exists():
        verb = "would create" if dry_run else "creating"
        print(f"{verb} empty folder {path} (keeps Finder's file out)")
        if not dry_run:
            path.mkdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gearth-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    base = gearth_dir(args.gearth_dir)
    if base is None:
        print("Pass --gearth-dir: the folder with G-Earth.exe or G-Earth.jar.", file=sys.stderr)
        return 1
    extensions = base / "Extensions"
    if not extensions.is_dir():
        print(f"{extensions} not found; start G-Earth once or check --gearth-dir", file=sys.stderr)
        return 1

    guard_ds_store(extensions, args.dry_run)
    old = sorted(p for p in extensions.iterdir() if p.is_dir() and p.name.startswith(FOLDER_PREFIX))
    if args.uninstall:
        for folder in old:
            print(f"{'would remove' if args.dry_run else 'removing'} {folder}")
            if not args.dry_run:
                shutil.rmtree(folder)
        return 0

    python = venv_python()
    if not python.exists():
        print(f"{python} not found; run `uv sync` first", file=sys.stderr)
        return 1
    command = [
        str(python),
        "-m",
        "__PKG__",
        "--project-dir",
        str(PROJECT),
        "-c",
        "{cookie}",
        "-p",
        "{port}",
        "-f",
        "{filename}",
    ]
    target = extensions / f"{FOLDER_PREFIX}{__version__}"
    content = json.dumps(command, separators=(",", ":"))
    print(f"{'would write' if args.dry_run else 'writing'} {target / 'command.txt'}:\n  {content}")
    if args.dry_run:
        return 0
    for folder in old:
        if folder != target:
            shutil.rmtree(folder)
    (target / "extension").mkdir(parents=True, exist_ok=True)
    (target / "command.txt").write_text(content, encoding="utf-8")
    print("Done. Restart G-Earth, then restart the Habbo client through it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
