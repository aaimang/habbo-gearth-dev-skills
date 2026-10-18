"""Outbox pacing with a real thread and a short interval."""

from __future__ import annotations

import threading
import time

from __PKG__.outbox import Outbox


def test_sends_in_order_with_a_gap():
    sent, done = [], threading.Event()

    def send(item):
        sent.append((item, time.monotonic()))
        if len(sent) == 3:
            done.set()

    box = Outbox(send, interval_s=0.05)
    box.start()
    for i in range(3):
        box.enqueue(i)
    assert done.wait(2)
    box.stop()
    assert [i for i, _ in sent] == [0, 1, 2]
    assert sent[2][1] - sent[0][1] >= 0.09


def test_pause_holds_sending():
    sent = []
    box = Outbox(sent.append, interval_s=0.0)
    box.pause_for(0.3)
    box.start()
    box.enqueue("x")
    time.sleep(0.1)
    assert sent == []
    time.sleep(0.4)
    box.stop()
    assert sent == ["x"]


def test_full_queue_drops_without_blocking():
    box = Outbox(lambda item: None, max_queue=1)  # not started: nothing drains
    assert box.enqueue(1) and not box.enqueue(2)
