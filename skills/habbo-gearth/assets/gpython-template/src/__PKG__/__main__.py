"""Entry point G-Earth runs: ``python -m __PKG__ -c {cookie} -p {port} -f {filename}``.

Logs go to ``<project>/logs/__PKG__.log`` (rotated) and stderr. G-Earth's ▶ button
raises ``double_click``; the console shows :meth:`App.notice` lines.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import signal
import sys
import threading
from pathlib import Path

from . import __version__
from .app import App
from .gpython import Extension
from .guard import configure_dump_dir

log = logging.getLogger("__PKG__")

EXTENSION_INFO = {
    "title": "__TITLE__",
    "description": "__DESC__",
    "version": __version__,
    "author": "__AUTHOR__",
}


def setup_logging(project_dir: Path, debug: bool = False) -> None:
    """Rotating file log plus stderr (G-Earth shows neither; read the file)."""
    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(threadName)s %(name)s: %(message)s")
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "__PKG__.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream)
    configure_dump_dir(log_dir / "bad-packets")


def start_extension(ext: Extension, stop: threading.Event) -> bool:
    """``ext.start()`` with an escape hatch.

    g-python 0.1.6 blocks in ``start()`` on a barrier until G-Earth sends INIT. If G-Earth
    refuses the connection (the "allow this extension?" prompt is declined) the socket
    closes and ``start()`` would hang forever, so watch for that and break the barrier.
    Uses 0.1.6's private attributes: re-check them if you ever change the pin.

    Returns:
        ``True`` if connected to G-Earth.
    """
    errors: list[BaseException] = []

    def run() -> None:
        try:
            ext.start()
        except BaseException as exc:  # noqa: BLE001 - handed to the caller
            errors.append(exc)

    thread = threading.Thread(target=run, name="gearth-start", daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(0.5)
        sock = getattr(ext, "_Extension__sock", None)
        if stop.is_set() or (sock is not None and ext.is_closed()):
            barrier = getattr(ext, "_Extension__start_barrier", None)
            if barrier is not None:
                barrier.abort()
            thread.join(1.0)
            return False
    if errors:
        raise errors[0]
    return not ext.is_closed()


def main(argv: list[str] | None = None) -> int:
    """Run until G-Earth closes the connection (the store requires the process to exit)."""
    parser = argparse.ArgumentParser(
        prog="__PKG__",
        description=EXTENSION_INFO["description"],
    )
    parser.add_argument("-p", "--port", required=True, help="G-Earth's extension port")
    parser.add_argument("-c", "--auth-token", dest="cookie", default=None, help="G-Earth's cookie")
    parser.add_argument("-f", "--filename", default=None, help="extension folder name")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    setup_logging(args.project_dir.expanduser().resolve(), args.debug)
    log.info(
        "__TITLE__ %s starting (port %s)",
        __version__,
        args.port,
    )

    gearth_args = ["-p", str(args.port)]
    if args.cookie:
        gearth_args += ["-c", args.cookie]
    if args.filename:
        gearth_args += ["-f", args.filename]
    ext = Extension(EXTENSION_INFO, gearth_args, {"use_click_trigger": True}, silent=True)
    app = App(ext)
    app.register()

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        if not start_extension(ext, stop):
            log.warning("G-Earth refused or closed the connection")
            return 1
    except OSError as exc:
        log.error("can't reach G-Earth on port %s: %s", args.port, exc)
        return 1
    log.info("connected to G-Earth")
    while not stop.is_set() and not ext.is_closed():
        stop.wait(0.5)
    app.outbox.stop()
    log.info("bye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
