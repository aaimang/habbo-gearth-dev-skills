"""Habbo's own windows for the user: notification bubbles and popups.

These are made-up incoming packets sent to the user's client with ``send_to_client``.
Nothing goes to the server, so only the user sees them. Sends run on one
``ext-notify`` thread, never on G-Python's callback thread.

``NotificationDialog`` is ``s type, i[s key, s value]``. Checked on the live AIR client
(MAC63, 2026-10) with Developer mode on:

* ``display=BUBBLE``: a toast at the top right that fades by itself. Shows ``image``;
  prints HTML tags as text, so plain text only.
* ``display=POP_UP``: a window with a title and a close button. Shows ``image`` on the
  left, a ``linkUrl``/``linkTitle`` link-button, line breaks, and ``<b>``, ``<i>``,
  ``<u>`` and ``<font color>``. Escape anything that isn't yours with :func:`escape`.

``image`` takes a full HTTPS URL or ``${image.library.url}album1584/<BADGE>.gif``.
"""

from __future__ import annotations

import html
import logging
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from .gpython import Direction, HPacket
from .guard import guarded

log = logging.getLogger(__name__)

DIALOG_TYPE = "extension"
BADGE_URL = "${image.library.url}album1584/"
GREEN = "#2E7D32"
RED = "#C62828"
BUBBLE_MAX = 160
POPUP_MAX = 1500
QUEUE_MAX = 20
SEND_GAP_S = 0.3

_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")


def clean(text: str, limit: int, *, multiline: bool = False) -> str:
    """Remove control characters and cut text to ``limit`` characters (ends in ``…``)."""
    text = text.replace("\r\n", "\n")
    if not multiline:
        text = text.replace("\n", " ")
    text = _CONTROL.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def escape(text: str) -> str:
    """Make text safe inside a popup, which reads ``<``, ``>`` and ``&`` as markup."""
    return html.escape(text, quote=True)


def colour(text: str, color: str) -> str:
    """Popup markup for coloured text (``text`` must already be escaped)."""
    return f'<font color="{color}">{text}</font>'


def badge(code: str) -> str:
    """Image URL of a Habbo badge, e.g. ``badge("ADM")``; the client expands it."""
    return f"{BADGE_URL}{code}.gif"


def build_dialog(params: dict[str, str], dialog_type: str = DIALOG_TYPE) -> HPacket:
    """An incoming ``NotificationDialog`` with these keys (``display``, ``message``, ...)."""
    values: list[Any] = [dialog_type, len(params)]
    for key, value in params.items():
        values += [key, value]
    return HPacket("NotificationDialog", *values)


def _extras(image: str | None, link: tuple[str, str] | None) -> dict[str, str]:
    extra: dict[str, str] = {}
    if image:
        extra["image"] = image
    if link:
        extra["linkUrl"], extra["linkTitle"] = link
    return extra


def build_bubble(message: str, *, title: str = "", image: str | None = None) -> HPacket:
    """A bubble: the small box at the top right that fades by itself.

    Args:
        message: Plain text (bubbles show HTML tags as they are).
        title: Put before the text as ``title: message``.
        image: Icon URL.

    Returns:
        The packet.
    """
    text = clean(f"{title}: {message}" if title else message, BUBBLE_MAX)
    return build_dialog({"display": "BUBBLE", "message": text, **_extras(image, None)})


def build_popup(
    message: str,
    *,
    title: str,
    image: str | None = None,
    link: tuple[str, str] | None = None,
) -> HPacket:
    """A popup: a window that stays until the user closes it.

    Args:
        message: Text with ``\\n`` line breaks; may use ``<b>``, ``<i>``, ``<u>`` and
            ``<font color>``, so pass anything that isn't yours through :func:`escape`.
        title: The window title.
        image: Picture URL, shown on the left.
        link: ``(url, title)`` for a link-button; it opens the system browser.

    Returns:
        The packet.
    """
    return build_dialog(
        {
            "display": "POP_UP",
            "title": clean(title, 60),
            "message": clean(message, POPUP_MAX, multiline=True),
            **_extras(image, link),
        }
    )


class HotelNotifier:
    """Sends windows to the user's client: throttled, bounded, on its own thread."""

    def __init__(
        self,
        ext: Any,
        *,
        enabled: Callable[[str], bool] = lambda kind: True,
        min_gap_s: float = 10.0,
        fallback: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        gap_s: float = SEND_GAP_S,
    ) -> None:
        """Prepare; call :meth:`start` to begin sending.

        Args:
            ext: The G-Python ``Extension`` (or a fake in tests).
            enabled: Whether a kind of bubble may show (e.g. read a config toggle).
            min_gap_s: Seconds before the same bubble may show again.
            fallback: Called once per session when the client can't take a window,
                e.g. to write to G-Earth's console instead.
            clock: Monotonic clock; injectable for tests.
            gap_s: Pause between two sends.
        """
        self._ext = ext
        self._enabled = enabled
        self._min_gap_s = min_gap_s
        self._fallback = fallback
        self._clock = clock
        self._gap_s = gap_s
        self._queue: deque[HPacket] = deque(maxlen=QUEUE_MAX)  # full: oldest dropped
        self._last: dict[str, float] = {}
        self._cond = threading.Condition()
        self._stop = False
        self._failed = False
        self._thread: threading.Thread | None = None

    def notify(self, kind: str, message: str, key: str | None = None, **bubble: Any) -> bool:
        """Queue a bubble unless ``kind`` is off or the same one showed recently.

        Args:
            kind: A category the user can turn off (``enabled(kind)``).
            message: The text.
            key: Identifies repeats; ``kind:message`` if not given.
            **bubble: ``title`` / ``image`` for :func:`build_bubble`.

        Returns:
            ``True`` if it was queued.
        """
        if not self._enabled(kind):
            return False
        key = key or f"{kind}:{message}"
        now = self._clock()
        with self._cond:
            last = self._last.get(key)
            if last is not None and now - last < self._min_gap_s:
                return False
            self._last[key] = now
        return self.send(build_bubble(message, **bubble))

    def send(self, packet: HPacket) -> bool:
        """Queue any client-bound packet (popups the user asked for go here directly)."""
        with self._cond:
            self._queue.append(packet)
            self._cond.notify()
        return True

    def clear(self) -> None:
        """Forget queued windows and repeat timers (call on ``connection_end``)."""
        with self._cond:
            self._queue.clear()
            self._last.clear()
            self._failed = False

    def start(self, name: str = "ext-notify") -> None:
        """Start the sender thread (once)."""
        if self._thread is None:
            self._thread = threading.Thread(target=guarded(self._run), name=name, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the thread; unsent windows are dropped."""
        with self._cond:
            self._stop = True
            self._cond.notify()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def flush(self) -> None:
        """Send everything queued now, on the calling thread (tests)."""
        while True:
            with self._cond:
                if not self._queue:
                    return
                packet = self._queue.popleft()
            self._deliver(packet)

    def _run(self) -> None:
        while True:
            with self._cond:
                while not self._queue and not self._stop:
                    self._cond.wait()
                if self._stop:
                    return
                packet = self._queue.popleft()
            self._deliver(packet)
            time.sleep(self._gap_s)

    def _deliver(self, packet: HPacket) -> None:
        # g-python 0.1.6's send_to_client never raises and returns None: a name G-Earth
        # doesn't know only prints "Could not send incomplete packet" to stderr. So check
        # the catalogue first; a False return (other versions) counts as a failure too.
        name = packet.incomplete_identifier
        infos = getattr(self._ext, "packet_infos", None) or {}
        ok = False
        if name in infos.get(Direction.TO_CLIENT, {}):
            try:
                ok = self._ext.send_to_client(packet) is not False
            except Exception:
                log.debug("send_to_client failed", exc_info=True)
        if ok:
            return
        log.info("couldn't show %s in the client", name)
        with self._cond:
            first, self._failed = not self._failed, True
        if first and self._fallback is not None:
            self._fallback(f"Couldn't show {name} in the client; messages stay in this console.")
