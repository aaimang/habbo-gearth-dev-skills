# Bugs and workarounds (symptom first)

Every entry happened for real in a shipped G-Python extension (2026-10, G-Earth 1.5.4, G-Python 0.1.6,
macOS AIR builds MAC63-2026101x) unless marked. Search this file for the symptom.

## Contents
1. Triage: 60-second decision tree
2. G-Earth and connection
3. Sending
4. Parsing and the live client
5. G-Python
6. Chat-bot behaviour
7. Installing and updating
8. Desktop UI (Tkinter) on macOS / Windows
9. Tests and CI

## 1. Triage

```
Is G-Earth's window open?
├─ no (macOS) ─> .DS_Store FILE in Extensions/  (2.1)
└─ yes
   Is the extension listed / green in the Extensions tab?
   ├─ no ─> command.txt path wrong, venv missing, crash on start: run its command by hand (2.2)
   └─ yes
      Does the extension's log show the game connection (host, client type, hotel version)?
      ├─ no ─> restart the game client through G-Earth (2.3)
      └─ yes
         Do intercepts fire (debug log per packet)?
         ├─ no ─> name not in packet_infos (wrong name / wrong client type) (4.6), or the packet thread died (5.1)
         └─ yes
            Do sends arrive?
            ├─ no ─> packet safety: Developer mode or do it once by hand (3.1)
            └─ yes, but wrong ─> layout drift / encoding (section 4)
```

## 2. G-Earth and connection

**2.1 G-Earth runs but its window never opens (macOS).** `~/Library/Logs/G-Earth/app.log`
ends with `Running extension .../Extensions/.DS_Store`. Finder writes `.DS_Store` into
every folder you open; G-Earth tries to start every entry in `Extensions/`, finds no
command, and JavaFX start-up dies with a NullPointerException
(`ExecutionInfo.getExecutionCommand` returns null). Fix: `rm` the file and create an
empty **folder** named `.DS_Store` (Finder can't overwrite it; G-Earth logs an
IOException for a folder without `command.txt` and carries on; the store's Installed tab
skips names without `_`). Installers should do this on every run. Never tell users to
browse that folder in Finder.

**2.2 Extension not listed / dies at once.** Run the exact argv from `command.txt` in a
terminal with `-p 9092`. Usual causes: relative paths (G-Earth runs commands from
`extension/`), a venv that doesn't exist yet (`uv sync`), the shell `PATH` not being
inherited (use absolute paths; locate `uv`/`git` yourself), missing config/env file
(pass `--project-dir`).

**2.3 Extension connected to G-Earth but never sees the hotel.** After restarting
G-Earth, the game client must be restarted through it too. No `connection_start` means
no packets and no packet names.

**2.4 `start()` hangs forever.** The user declined the "allow this extension?" prompt
(no cookie when run by hand) or G-Earth closed the socket; G-Python 0.1.6 waits on a
barrier. Fix: run `start()` on a thread and abort the barrier when the socket closes
(template `start_extension`).

**2.5 Extension keeps running after G-Earth closes.** Loop on `ext.is_closed()` and exit;
the store requires it. `fake_gearth.py` checks it.

## 3. Sending

**3.1 Sends silently do nothing.** G-Earth's packet safety drops headers it hasn't seen
in that direction since it started (per hotel version), unless Developer mode is on.
Expressions don't bypass it. Fix: tell the user to enable Developer mode (Extra tab), or
to perform each action once by hand. Surface it: a console notice on connect listing the
actions to do once.

**3.2 Worse after every reconnect.** The extension kept its own "seen headers" list and
reset it on reconnect, while G-Earth keeps its list for its whole run, so the extension
blocked sends G-Earth would allow. Fix: send and let G-Earth decide.

**3.3 "Could not send packet because G-Earth isn't connected to a client" on stderr.**
Sent before `connection_start` or after `connection_end`. Queue until connected; clear on
end. `send_*` returns None either way: you're never told, so log before sending.

**3.4 Account muted / bubbles lost.** Flood control. Pace sends (one bubble per ~1.5 s),
honour `FloodControl` and `RemainingMutePeriod` by pausing the outbox for that many
seconds, cap bubbles per answer.

**3.5 Whispered (private) answer appeared in public chat.** A fallback from whisper to chat
when whispers weren't sendable yet. Never fall back for private content.

**3.6 Chat text cut or rejected.** 100-character bubble limit counted in UTF-16 units
(emoji = 2). Split at word boundaries before sending.

**3.7 HC-only actions do nothing.** Dances 2-4 and expressions 2/3/6 need Habbo Club.
Make them opt-in; default to wave (1), thumbs up (7), dance 1.

## 4. Parsing and the live client

**4.1 "truncated string" in `UserUpdate`; sit/sign never detected.** Live AIR sends an
extra int after head/body direction in each entry. One entry: the extra int is read as
an empty status (silent loss). Several entries: misaligned. Found by hex-dumping the
first bad packet (12 zero bytes between height and status where 8 were expected). Fix:
try the live layout (1 extra int) first, documented (0) second; accept only a full,
plausible parse.

**4.2 Everyone after one entry missing from `Users`.** Player entries end with an extra
int (-1) after `isModerator`. Fix: live tail first, documented second, and if a tail still
doesn't fit, scan forward to the next plausible entry header instead of giving up.

**4.3 Fallback picked the wrong layout.** "Most entries parsed" chose the documented
layout, which can "decode" an entry by misreading the extra int as an empty status.
Fix: the documented layout wins only on a complete, clean parse.

**4.4 The log dump cut off the interesting part.** Save the whole first bad packet per type
per session to `logs/bad-packets/<Name>-<time>.hex`; log the path. Decode with
`habbo_packets.py decode --file`.

**4.5 Wrong theory: "G-Earth garbles bytes / delivers the wrong packet type".** Ruled out
from G-Earth's source: transport is byte-exact (Latin-1 both ways) and names map 1:1 to
ids. Lesson: compare a capture with the layout before blaming the tools.

**4.6 Intercept never fires.** The name isn't in `packet_infos` for this client (typo,
renamed packet, different client type). Check on `connection_start` and log missing
names; look up the right one with `habbo_packets.py search` and Sulek.

**4.7 Garbled accents/emoji.** G-Python's `read_string` defaults to Latin-1. Decode UTF-8.

**4.8 HabboPackets layout doesn't decode a real packet.** Custom/enum layouts in
HabboPackets are estimates and not always in wire order (`Users` discriminator placement,
`UserUpdate` status shown as typed actions instead of a string). Use the wire layouts in
packets.md, then verify with a capture.

**4.9 Room state empty after an extension restart.** The extension only learns users when
the room loads; `GetHeightMap` (which G-Python's `RoomUsers.request()` sends) no longer
exists. Fix: remember the last room id and send `GetGuestRoom(id, 0, 1)` on start, or ask
the user to re-enter.

## 5. G-Python

**5.1 Everything froze / stopped.** A callback blocked (network call, sleep) or raised.
One thread runs all callbacks and G-Earth waits for each. Guard every callback, move
slow work to workers, avoid `async` intercept modes (they share the packet object).

**5.2 GitHub version won't import.** Circular import on `master`. Pin `g-python==0.1.6`.

**5.3 `SyntaxWarning: "is not" with a literal` on Python 3.12+.** Harmless (0.1.6 source).
Import through a shim that suppresses it; add a pytest filter.

**5.4 `HBubble` has no members.** Written with `:` instead of `=`. Use ints.

## 6. Chat-bot behaviour (LLM-backed bots)

**6.1 Money spent on answers that couldn't be sent.** Check sendability (reply mode,
cooldown, budget) before the API call.

**6.2 Answers too long.** "At most N characters" reads as a target. Ask for "as briefly as
possible; a simple question gets one short sentence" and cap bubbles in code.

**6.3 "Let me look that up" in answers (web search).** Keep only the text after the last
search step.

**6.4 Model output starting with `/` or `:` or containing links.** The client may treat it
as a command; links are against chat norms. Sanitise in code, not only in the prompt.

**6.5 Prompt injection from room chat or web results.** Treat all room text as untrusted;
the bot speaks from the user's account, so filter output (links, commands), whitelist who
can trigger it, rate-limit per user and per target.

## 7. Installing and updating

**7.1 Config typo stops the extension.** Strict config parsing (rejecting unknown keys) is
good, but the error should name the key and suggest the closest valid one.

**7.2 Update applied but old version still runs.** The running process keeps its code;
G-Earth's cookie is single-use, so no self-restart. Tell the user to restart G-Earth (and
then the client).

**7.3 One-click updater pulled unreleased commits.** Fast-forwarding to `origin/main`
installs whatever is there. Fast-forward to the **release tag's commit**, after checking
the tag matches `^v\d+\.\d+\.\d+$`, is on `origin/main`, HEAD is its ancestor, and the
version file at the tag equals the target. Never `--force` tag fetches.

**7.4 Updater leaked secrets to child processes.** `load_dotenv` puts API keys in
`os.environ`, which `subprocess` inherits (git hooks, build scripts). Strip secret
variables (e.g. `ANTHROPIC_*`) from the child environment.

**7.5 git/uv "not found" when started by G-Earth.** No shell `PATH`. Search known install
folders (`~/.local/bin`, `~/.cargo/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, the
Python's own `bin`/`Scripts`) and drop `VIRTUAL_ENV` from the child env.

**7.6 Updater refused on a clean checkout.** `git status --porcelain` lines keep a leading
space; don't `strip()` the output before slicing `[3:]`.

**7.7 Windows: `uv sync` fails during an update.** Files of the running process are locked.
Tell the user to close G-Earth and run `uv sync`.

## 8. Desktop UI (Tkinter) opened from G-Earth's ▶

**8.1 macOS: window crashes or never shows.** Tk must own the main thread; `double_click`
runs on a G-Python event thread. Queue a request for the main thread.

**8.2 macOS: window opens behind other apps / Dock shows "Python".** Activate the app via
`NSApplication` (ctypes/objc), set `-topmost` until focused, set `CFBundleName` before the
first `tk.Tk()`, re-apply `iconphoto` after activation and again ~150 ms later.

**8.3 Window left half-open on close.** `root.after_cancel(id)` also deletes the Tcl
command and fails for timers other widgets registered, skipping `destroy()`. Cancel at
the Tcl level: `root.tk.call("after", "cancel", id)`.

**8.4 Windows: empty `TclError` loading an image.** Intermittent after several Tk windows.
Read PNG bytes yourself, pass `data=`, retry once, and open without the image if it
still fails. Set an AppUserModelID so the taskbar shows your icon.

**8.5 A buffer object treated as missing.** A class defining `__len__` is falsy when empty;
use `is not None`.

## 9. Tests and CI

**9.1 CI can't import Tk modules.** Runner Pythons often lack Tkinter (Ubuntu system
Python, Homebrew Pythons). Never import Tk-using modules at test-module top level; use
`pytest.importorskip("tkinter")`. Docs builds on Ubuntu: `apt-get install python3-tk`.
Simulate locally with a fake `tkinter` package raising
`ModuleNotFoundError(name="_tkinter")` on `PYTHONPATH`.

**9.2 Suite suddenly slow.** A thread `stop()` that waits for a poll timeout. Put a wake-up
item on the queue.

**9.3 Test failure that looked like a bot bug.** The test advanced a fake clock past the
staleness limit before the action was queued. Order the fake-clock steps like reality.

**9.4 Docs warning hidden by incremental builds.** Build docs into a fresh folder with
`-E -W --keep-going -n`.
