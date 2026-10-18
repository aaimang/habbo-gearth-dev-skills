# G-Python: API, threading model, traps, and the architecture that works

G-Python (https://github.com/sirjonasxx/G-Python, PyPI `g-python`) is the Python
extension API for G-Earth. Everything here was checked against the installed 0.1.6
source (`site-packages/g_python/`), and proven in a G-Python extension that ran for
weeks against the live client.

## Contents
1. Install and pin
2. API surface
3. The threading model (the one rule)
4. Architecture that works
5. Reading and building packets
6. Traps in 0.1.6 and their fixes
7. A minimal correct extension

## 1. Install and pin

- `g-python==0.1.6` from PyPI, **pinned**. GitHub `master` has a circular import between
  `hpacket.py` and `gextension.py` and won't import. 0.1.6 has no dependencies and needs
  G-Earth >= 1.4.1 (it prints a warning saying so unless `silent=True`).
- Python 3.11+ is fine. On 3.12+, 0.1.6 prints harmless `SyntaxWarning`s (`is not 'NULL'`):
  import G-Python through one shim module that silences them (template `gpython.py`).
  In pytest: `filterwarnings = ["ignore::SyntaxWarning"]`.
- **uv is required** for development (https://docs.astral.sh/uv/getting-started/installation/): `uv sync` builds the project's `.venv`
  and `uv.lock`; `uv run pytest` / `uv run ruff` run the checks. `command.txt` points at
  `.venv/bin/python` (`.venv\Scripts\python.exe` on Windows). G-Earth's launch
  environment has no shell `PATH`, so uv isn't needed at runtime, only the venv it made.

## 2. API surface

```python
from g_python.gextension import Extension     # import via your shim in real code
from g_python.hdirection import Direction       # Direction.TO_CLIENT (in) / TO_SERVER (out)
from g_python.hmessage import HMessage          # .packet, .direction, .is_blocked, .index()
from g_python.hpacket import HPacket

ext = Extension(
    {"title": "X", "description": "...", "version": "1.0.0", "author": "me"},  # all 4 required
    ["-p", "9092", "-c", cookie, "-f", filename],     # parsed for -p/--port, -c/--auth-token, -f/--filename
    {"use_click_trigger": True, "can_leave": True, "can_delete": True},  # optional settings
    silent=True,
)
ext.intercept(Direction.TO_CLIENT, callback, "Chat")       # by NAME; mode="default"
ext.on_event("connection_start", fn)                         # also: init, connection_end, double_click
ext.start()                                                  # blocks until INIT (and CONNECTION_START if G-Earth asks)
ext.send_to_server(HPacket("Chat", "hi", 0, -1))             # returns None: you're never told if it was dropped
ext.send_to_client(HPacket("Whisper", ...))                  # only your client sees it
ext.write_to_console("text", "blue")                         # G-Earth's extension console
ext.connection_info  # {host, port, hotel_version, client_identifier, client_type} or None
ext.packet_infos     # {Direction: {id|name|hash: [ {Id, Name, Hash, Structure, Source} ]}} or None
ext.is_closed(); ext.stop()
```

| Event | When | Thread |
|---|---|---|
| `init` | G-Earth accepted the extension | new thread per event |
| `connection_start` | the game connected; `packet_infos` now set | new thread |
| `connection_end` | the game disconnected; info cleared | new thread |
| `double_click` | user pressed ▶ (needs `use_click_trigger=True`) | new thread |

Intercept modes: `default` (blocking, can modify/block: use this), `async` (a thread
per packet sharing the same packet object: racy), `async_modify` (blocks, then re-sends:
can reorder packets). Avoid the async modes; do your own queueing instead.

`HPacket`: `HPacket("Name", *values)` appends `str` (UTF-8), `int` (int32), `bool`,
`bytes` in order; the name is resolved to an id at send time from `packet_infos`.
`HPacket.from_bytes(raw)` for tests. Reading: `read_int`, `read_short`, `read_long`,
`read_bool`, `read_byte`, `read_string(encoding=...)`, `read("isB")`; `read_index` starts
at 6 and is reset after each callback. Writing: `replace_int/short/bool/string`,
`append_*`; set `message.is_blocked = True` to drop a packet.

## 3. The threading model (the one rule)

- One reader thread reads G-Earth's socket.
- **One packet thread runs every intercept callback, one after another.** After all
  callbacks for a packet return, it answers G-Earth (MANIPULATED_PACKET).
- **G-Earth holds the packet until then.** So:
  - a slow callback (network call, sleep, lock wait, `send` that waits on G-Earth) freezes
    the game for everyone in that direction;
  - an uncaught exception **kills the packet thread**: no more packets ever reach the
    extension and G-Earth keeps waiting for answers. There is no exception handling in
    0.1.6.

**Rule: callbacks only parse, decide, and enqueue. Wrap every callback in a catch-all
guard.** Network calls (LLM, HTTP, Web API), sending, sleeping, file writes: other threads.

`scripts/fake_gearth.py` prints how long each intercept took and flags anything over
50 ms.

## 4. Architecture that works

```
G-Earth ── socket ──> G-Python reader ──> packet thread ──> guarded callbacks
                                                              │ parse (bounds-checked, UTF-8)
                                                              │ update small in-memory state (lock)
                                                              └─> queue.put(job) ─────────────┐
                                                                                              v
   worker pool (ThreadPoolExecutor, 1-2 workers): slow work (LLM APIs, HTTP), gated by
   whitelist -> cooldown -> budget -> queue size, cheapest check first
                                                              │
                                                              v
   Outbox thread: ONE sender, paced (~1.5 s between chat bubbles), honours FloodControl /
   RemainingMutePeriod pauses, drops stale items, never blocks callers
                                                              │
                                                              v
                                       ext.send_to_server(HPacket("Name", ...))
```

Proven details:
- **Guard** (`guard.py`): `ProtocolError` -> log the first bad packet per handler with a
  hex excerpt and save it whole to `logs/bad-packets/<Name>-<time>.hex`; any other
  exception -> `log.exception`. Never re-raise.
- **State** (room users by index, own index/name, floor tiles): small dataclasses behind
  a lock; rebuilt on `connection_start` and room entry.
- **Gate before spending**: check everything cheap (whitelist, can-this-reply-mode-be-sent,
  cooldowns, budget) *before* queueing expensive work, and refund cooldowns if the
  failure wasn't the user's fault.
- **Never fall back from whisper to public chat** for private answers.
- **Rate limits**: per-user and per-target cooldowns, one in-flight request per user, a
  daily budget, a bounded queue.
- **Avatar automation** on its own thread: at most one action every ~1.5 s, drop queued
  actions older than ~5 s, pause automation when the user acts by hand.
- **Main thread**: waits for the session to end. On macOS a Tk window must own the main
  thread, so `double_click` only queues a "show window" request for it.
- **Logging**: rotating file in the project's `logs/` (G-Earth shows no stderr), thread
  names in the format, one INFO line per command with outcome and latency.

## 5. Reading and building packets

- **Strings**: `read_string()` and `read("s")` decode **Latin-1**; Habbo is UTF-8. Read the
  u16 length and decode the bytes yourself, rejecting lengths that run past the end
  (template `protocol.Reader.str`). `append_string` already encodes UTF-8.
- **Bounds**: past the end, `read_int()` silently returns a wrong number (it converts
  whatever bytes are left) and `read_string()` returns a short string: no error at all.
  Check `remaining` first and raise your own `ProtocolError` so the guard can dump it.
- **Names, not ids**: `HPacket("Chat", ...)`, `intercept(..., "Chat")`. Check
  `name in ext.packet_infos[direction]` on `connection_start` and warn once per missing
  name (template `App.known`).
- **Index vs id**: room packets use the room index; keep an index -> user map from
  `Users`/`UserRemove`.
- **Own echo**: your outgoing chat is intercepted as `out:Chat`, and comes back as
  `in:Chat` with your index. Handle commands from the outgoing packet; ignore the echo.
- **Blocking your own command** (`message.is_blocked = True` in an `out:Chat` callback)
  hides it from the room.

## 6. Traps in 0.1.6 and their fixes

| Trap | Effect | Fix |
|---|---|---|
| `start()` waits on a barrier for INIT | hangs forever if the user declines the allow prompt or G-Earth closes the socket | run `start()` on a thread, watch `ext.is_closed()`, abort `_Extension__start_barrier` (template `start_extension`) |
| No exception handling in callbacks | one bug stops all packet flow | `guarded()` wrapper on every intercept and event |
| `read_string` defaults to Latin-1 | accents and emoji garbled | own UTF-8 reader |
| `HBubble` enum written with `:` | has no members | use plain ints for bubble styles |
| `hash is not 'NULL'` | `'NULL'` never becomes `None`; SyntaxWarning on 3.12+ | harmless; silence via the shim |
| `htools.RoomUsers` sends `GetHeightMap` | packet no longer exists in AIR | track users yourself from `Users` / `UserRemove`; rejoin with `GetGuestRoom(id, 0, 1)` |
| `hparsers` (`HEntity`, `HUserUpdate`) | documented layouts + Latin-1; break on live drift | own parsers with layout variants |
| Sending before `connection_start`, or an unknown name | dropped with a line on stderr only (`send_*` returns None) | queue until connected; check names on connect; drop the queue on `connection_end` |
| `send_to_server("{expr}")` | round trip to G-Earth to convert | build `HPacket` locally |

## 7. A minimal correct extension

The full, tested version is `assets/gpython-template/` (create one with
`scripts/scaffold.py`). The essential shape:

```python
import logging, queue, sys, threading
from my_ext.gpython import Extension, Direction, HPacket   # shim silences SyntaxWarnings
from my_ext.guard import guarded                            # catch-all wrapper
from my_ext.protocol import Reader                          # UTF-8, bounds-checked

log = logging.getLogger("my_ext")
jobs: "queue.Queue[str]" = queue.Queue(maxsize=50)

def on_own_chat(msg):                       # packet thread: fast, never raises
    r = Reader(msg.packet)
    text = r.str()
    if text.startswith("!echo "):
        msg.is_blocked = True
        try:
            jobs.put_nowait(text[6:][:100])
        except queue.Full:
            log.warning("busy, dropped")

def sender(ext, stop):                      # its own thread: paced sending
    while not stop.is_set():
        try:
            text = jobs.get(timeout=0.5)
        except queue.Empty:
            continue
        ext.send_to_server(HPacket("Chat", text, 0, -1))
        stop.wait(1.5)

ext = Extension({"title": "Echo", "description": "d", "version": "1.0.0", "author": "me"},
                sys.argv, silent=True)
ext.intercept(Direction.TO_SERVER, guarded(on_own_chat), "Chat")
stop = threading.Event()
threading.Thread(target=sender, args=(ext, stop), daemon=True).start()
ext.start()                                 # use start_extension() from the template in real code
while not ext.is_closed():
    stop.wait(0.5)
stop.set()
```
