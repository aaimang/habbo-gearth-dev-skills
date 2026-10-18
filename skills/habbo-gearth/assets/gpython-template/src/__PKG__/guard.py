"""Exception guard for G-Python callbacks, and capture of packets that don't parse.

G-Python runs every intercept callback on ONE thread with no exception handling, and
G-Earth holds each packet until the callback returns. An uncaught error kills that
thread (all packet flow stops); a slow callback freezes the game. Every callback goes
through :func:`guarded`.

A packet that doesn't match its layout is a data problem, not a crash: the first one per
handler is logged with a hex excerpt and saved whole to the dump folder
(``logs/bad-packets/<Name>-<time>.hex``). Decode it with the skill's
``habbo_packets.py decode --file ...``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .protocol import ProtocolError

log = logging.getLogger(__name__)

_reported: Counter[str] = Counter()
_lock = threading.Lock()
_dump_dir: Path | None = None


def configure_dump_dir(path: Path | None) -> None:
    """Set where whole bad packets are saved (``None`` turns saving off)."""
    global _dump_dir
    _dump_dir = path


def _save(name: str, raw: bytes, problem: str) -> Path | None:
    if _dump_dir is None or not raw:
        return None
    try:
        _dump_dir.mkdir(parents=True, exist_ok=True)
        path = _dump_dir / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.hex"
        lines = [f"# {name}: {problem}", f"# {len(raw)} bytes"]
        lines += [raw[i : i + 32].hex(" ") for i in range(0, len(raw), 32)]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except OSError as exc:
        log.debug("could not save bad packet: %s", exc)
        return None


def report_bad_packet(name: str, packet: Any, problem: str) -> None:
    """Warn (and save) the first bad packet per ``name``; later ones go to debug."""
    with _lock:
        _reported[name] += 1
        first = _reported[name] == 1
    raw = bytes(getattr(packet, "bytearray", b""))
    if not first:
        log.debug("%s packet didn't parse (%s)", name, problem)
        return
    saved = _save(name, raw, problem)
    header = int.from_bytes(raw[4:6], "big") if len(raw) >= 6 else -1
    log.warning(
        "%s packet didn't match the expected layout (%s); header=%d length=%d%s first bytes: %s",
        name,
        problem,
        header,
        len(raw),
        f" saved={saved}" if saved else "",
        raw[:64].hex(" "),
    )


def reset_reports() -> None:
    """Forget what was reported (call on each new game connection)."""
    with _lock:
        _reported.clear()


def guarded(fn: Callable[..., Any]) -> Callable[..., None]:
    """Wrap a callback so no exception escapes into G-Python's threads.

    Args:
        fn: The callback.

    Returns:
        A wrapper with the same name that never raises.
    """
    name = getattr(fn, "__name__", "handler")

    def wrapper(*args: Any) -> None:
        try:
            fn(*args)
        except ProtocolError as exc:
            packet = getattr(args[0], "packet", None) if args else None
            report_bad_packet(name, packet, str(exc))
        except Exception:
            log.exception("handler %s failed", name)

    wrapper.__name__ = name
    return wrapper
