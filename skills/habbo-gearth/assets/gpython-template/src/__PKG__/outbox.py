"""One sender thread with pacing, so the account doesn't trip Habbo's flood control.

Never send from a packet callback: queue here instead. The thread waits ``interval_s``
between packets and holds everything while :meth:`Outbox.pause_for` is active (call it
from ``FloodControl`` / ``RemainingMutePeriod``).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

Send = Callable[[Any], None]
_STOP = object()


class Outbox:
    """Paced, ordered sending on a daemon thread."""

    def __init__(
        self,
        send: Send,
        interval_s: float = 1.5,
        max_queue: int = 50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Prepare; call :meth:`start` to begin sending.

        Args:
            send: Sends one item (e.g. ``ext.send_to_server``).
            interval_s: Minimum gap between sends, in seconds.
            max_queue: Items beyond this are dropped (logged), never blocking callers.
            clock: Monotonic clock; injectable for tests.
        """
        self._send = send
        self._interval_s = interval_s
        self._clock = clock
        self._queue: queue.Queue[Any] = queue.Queue(max_queue)
        self._lock = threading.Lock()
        self._paused_until = 0.0
        self._last_sent = -interval_s
        self._thread: threading.Thread | None = None

    def start(self, name: str = "ext-outbox") -> None:
        """Start the sender thread (once)."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name=name, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the thread; unsent items are dropped."""
        if self._thread is not None:
            self.clear()
            self._queue.put(_STOP)
            self._thread.join(timeout)
            self._thread = None

    def enqueue(self, item: Any) -> bool:
        """Queue one packet; returns ``False`` (and logs) if the queue is full."""
        try:
            self._queue.put_nowait(item)
            return True
        except queue.Full:
            log.warning("outbox full, dropped a packet")
            return False

    def pause_for(self, seconds: float) -> None:
        """Hold all sending for ``seconds`` (flood control or a mute)."""
        with self._lock:
            self._paused_until = max(self._paused_until, self._clock() + seconds)

    def clear(self) -> None:
        """Drop everything not yet sent."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _wait_s(self) -> float:
        with self._lock:
            ready = max(self._paused_until, self._last_sent + self._interval_s)
        return max(0.0, ready - self._clock())

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            while (wait := self._wait_s()) > 0:
                time.sleep(min(wait, 0.25))
            try:
                self._send(item)
            except Exception:
                log.exception("send failed")
            with self._lock:
                self._last_sent = self._clock()
