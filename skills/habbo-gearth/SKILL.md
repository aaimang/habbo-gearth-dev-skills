---
name: habbo-gearth
description: Build, modify, debug, test and publish G-Earth extensions for Habbo (G-Python, G-Node, Java, G-Rust, xabbo), and read or write Habbo packets. Covers the extension protocol, packet names vs ids (Sulek), HabboPackets layouts and the live AIR client's drift from them, packet safety / Developer mode, threading rules, in-client bubbles and popups, installing via command.txt, the macOS .DS_Store crash, G-ExtensionStore submission rules, and reusable templates, scripts and prompts. Use whenever a task mentions G-Earth, G-Python, g_python, HPacket, Habbo packets, headers, packet layouts or hex dumps, intercepting/blocking/injecting packets, send_to_client, NotificationDialog, a popup or notification in the client, a Habbo bot, Sulek, HabboPackets, G-ExtensionStore, extension.json, or a chat bot or room helper running through G-Earth, even if the user only says "my Habbo extension" or "the packet doesn't parse". For room variables over REST (the official WIRED Web API), use habbo-wired-api instead.
license: MIT
compatibility: Agent Skills format (agentskills.io), e.g. Claude Code, Codex, Gemini CLI, Cursor. Scripts need Python 3.9+; G-Python development needs uv; packet lookups need network access (cached 7 days).
metadata:
  version: "1.1.0"
  release: V1
  updated: "2026-10-19"
  verified-against: "G-Earth 1.5.4 (G-Realm moon), g-python 0.1.6, Habbo AIR MAC63 2026-10 builds, HabboPackets 2026-09, G-ExtensionStore repo/1.5.3"
---

# Habbo G-Earth extensions (V1)

Everything needed to build G-Earth extensions that work against the **live** client:
the protocol, packet knowledge, failure modes already paid for, a tested project
template, and tools to look up, decode and validate. Distilled from shipping a G-Python
extension against the live client (2026-10) and from the G-Earth, G-Python, G-Rust,
HabboPackets and G-ExtensionStore sources.

## Ground rules (read first)

- **ToS:** G-Earth is a man-in-the-middle on the game connection; running it breaks
  Habbo's Terms of Service (sections 5 and 8). Say so plainly in docs and advice. When
  the goal is persistent room state (scores, levels, flags), use the official WIRED Web
  API instead (`habbo-wired-api` skill), alone or alongside a small extension.
- **What not to build:** anything that gives an unfair game/competition advantage,
  scams or trade manipulation, credential or account harvesting, harassment or spam
  tooling, ban/mute evasion, or bulk scraping of other players. G-ExtensionStore rejects
  these too. Room helpers, chat utilities, accessibility, logging your own activity,
  building tools and fun bots for consenting rooms are fine.
- **Other players' data** (names, mottos, chat) appears in logs, packet dumps and test
  fixtures: keep logs local, anonymise fixtures before committing, never publish dumps.
- **Secrets** (LLM API keys etc.) live in a gitignored env file, are never logged, never
  passed to child processes, never shipped in a store zip.

## Requirements

- **G-Python development needs [uv](https://docs.astral.sh/uv/getting-started/installation/).** The template, its installer, the tests and
  every workflow below use `uv sync` / `uv run`: uv creates the project's `.venv` (the
  Python G-Earth launches) and pins dependencies in `uv.lock`. Check with `uv --version`.
- Python 3.11+ for extensions. The skill's own `scripts/*.py` need only Python 3.9+ and
  no uv.

## Mental model

```
Habbo client ──> G-Earth (proxy, holds each packet) ──> hotel
                   │  TCP 127.0.0.1:9092 (framed messages, see gearth-runtime.md)
                   v
             your extension: ONE callback thread ──> queues ──> worker / outbox threads
```

G-Earth waits for the extension to answer every intercepted packet. Names (`Chat`) map
to per-build header ids, delivered when the game connects. G-Earth drops sends of
headers it hasn't seen yet unless Developer mode is on.

## Golden rules

**Do**
1. Address packets by **name** (`HPacket("Chat", ...)`, `intercept(..., "Chat")`). Ids
   change per build and differ between the Windows and macOS clients; the store bans them.
2. Keep callbacks **parse, decide, enqueue**. Wrap every callback (intercepts and events)
   in a catch-all guard. Slow work (LLM, HTTP, files) on workers; all sends from one
   paced outbox thread.
3. Read strings as **UTF-8** with bounds checks; G-Python reads Latin-1 and never reports
   truncation (a short `read_int` silently returns a wrong number).
4. Treat every documented layout as a hypothesis. **Verify with a capture**; parse the
   live layout first, documented second; accept only complete, plausible parses.
5. Save the first bad packet per type per session (`logs/bad-packets/*.hex`) and decode it
   with `scripts/habbo_packets.py decode`.
6. Check the names you need in `ext.packet_infos` on `connection_start`; tell the user
   (G-Earth console) what's missing, and what to do about packet safety.
7. Rate-limit: pace bubbles (~1.5 s), honour `FloodControl` / `RemainingMutePeriod`, cap
   queues, per-user cooldowns, budgets for paid APIs. Gate before spending.
8. Exit when the G-Earth socket closes. Rebuild state on each `connection_start`.
9. Use absolute paths in `command.txt` (G-Earth gives no shell PATH/env) and the
   project's own venv. Pin `g-python==0.1.6`.
10. Test without Habbo first: unit tests from bytes, fake Extension, then
    `scripts/fake_gearth.py`. Live-test on an alt account in a test room.

**Don't**
- Don't send from a callback, block, sleep, or call the network there.
- Don't use `mode="async"` intercepts (shared packet object) or G-Python's `hparsers` /
  `htools.RoomUsers` on AIR (Latin-1, old layouts, `GetHeightMap` is gone).
- Don't keep your own "seen headers" list that resets on reconnect; let G-Earth decide.
- Don't fall back from whisper to public chat for private output.
- Don't trust HabboPackets `custom`/estimated or enum layouts as wire order.
- Don't tell macOS users to open G-Earth's `Extensions` folder in Finder (`.DS_Store`).
- Don't self-restart after an update (single-use cookie): ask the user to restart
  G-Earth, then the client.

## Workflows

### A. New extension (G-Python)
1. Clarify: what triggers it (own chat, others' chat, room events), what it sends, which
   clients/OSes, how it will be distributed (GitHub installer vs store).
2. Pick the framework (`references/frameworks.md`); default G-Python for bots using
   Python libraries.
3. Check `uv --version` (install uv first if missing). Scaffold: `python3 scripts/scaffold.py --title "<Title>" --dest <dir> --description "..." --author <name>`
   (titles: > 4 chars, no `_` or `.`). Then `git init && uv sync && uv run pytest`.
4. List every packet: `python3 scripts/habbo_packets.py show <Name>`; note
   custom/estimated ones; capture and verify those before writing parsers.
5. Replace the example feature in `app.py`: parsers in `protocol.py` (tests from
   bytes), behaviour in `app.py` (tests with the fake Extension), sends via the outbox.
6. Verify: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`,
   `fake_gearth.py --run ...` with intercepts for each feature (no SLOW, exits on close).
7. Install: `uv run python scripts/install_gearth.py --dry-run`, then for real; restart
   G-Earth, then the client. Live checklist: `references/testing-and-release.md` section 5.

### B. Add or change packet handling
1. `habbo_packets.py show|search` for names, layouts, field meanings.
2. Capture a real packet (G-Earth logger or a bad-packet dump), anonymise it.
3. `habbo_packets.py decode --file x.hex --layout "..."` until every byte decodes sanely.
4. Parser with live-then-documented variants + fixture tests; register the intercept by
   name; add the name to the connect-time check.

### C. Debug "it doesn't work"
Follow the triage tree in `references/bugs-and-workarounds.md` section 1 (window opens?
listed? hotel connected? intercepts fire? sends arrive?). Read the extension's log file
and `logs/bad-packets/` directly rather than asking the user to paste. macOS G-Earth log:
`~/Library/Logs/G-Earth/app.log`.

### D. The client updated and parsing broke
1. Get the hotel version from the extension log (`connection_info["hotel_version"]`).
2. `habbo_packets.py id <Name> --build <version>` for each name used (renamed? gone?).
3. Decode new bad-packet dumps; add a layout variant; keep the old one as fallback.

### E. Publish to G-ExtensionStore
`references/extension-store.md`: rules, `extension.json` fields, Python packaging limits
(system `python`, only `g-python` available), then
`python3 scripts/validate_store_entry.py "<folder>" --first-submission` and a PR.

### F. Release and updates (GitHub-distributed)
`references/testing-and-release.md` sections 7-8: SemVer, every version location, tag,
CI, update checker against `releases/latest`, a one-click updater that installs the
**tag's** commit with the safety checks in bugs-and-workarounds 7.3-7.7.

### G. Show something in the client
No custom windows: only made-up incoming packets drawn by Habbo's own UI, seen by this
user only, with Developer mode on (`references/client-ui.md`).
1. Pick the window: `NotificationDialog` bubble (plain text, fades) for automatic
   notices, popup (`display=POP_UP`: title, `<b>`/`<font>`, image, link-button) for
   things the user asked for.
2. Use the template's `hotelui.py` (`build_bubble`, `build_popup`, `escape`,
   `HotelNotifier`): one notify thread, bounded queue, ~0.3 s gap, repeat throttle,
   name check before sending, console fallback once per session.
3. Owner commands: block the user's own `Chat`/`Shout`/`Whisper` when the first word is
   the prefix, then queue the window. Escape any dynamic text in popups.

## Tools (stdlib Python 3.9+, run from anywhere)

| Script | Use |
|---|---|
| `scripts/habbo_packets.py show Chat` | layout + fields (both directions), structures expanded, estimate warnings |
| `scripts/habbo_packets.py search avatar --dir out --templates` | find names and shared structures |
| `scripts/habbo_packets.py template UserUpdateMessageData` | one shared structure |
| `scripts/habbo_packets.py id Chat --build <hotelVersion>` | header id for an exact build (Sulek) |
| `scripts/habbo_packets.py decode --file x.hex --layout "i[i s s s i i i s i i s i i s s i b i]"` | decode bytes; reports leftovers or the failing offset |
| `scripts/habbo_packets.py selftest` | offline decoder checks |
| `scripts/fake_gearth.py --run "<cmd with {port}>" --intercept '{out:Chat}{s:"!ping"}{i:0}{i:-1}'` | end-to-end test: handshake, intercept timing, sends, console, exit on close |
| `scripts/scaffold.py --title ... --dest ...` | new project from `assets/gpython-template/` |
| `scripts/validate_store_entry.py <folder> [--first-submission]` | G-ExtensionStore CI rules + review smells |

Data is cached in `~/.cache/habbo-gearth/` for 7 days (`--refresh` to re-download).

## Reference map (read only what the task needs)

| File | Read when |
|---|---|
| `references/gearth-runtime.md` | protocol messages, `Extensions/` layout and paths per OS, Sulek, packet safety, expressions, install paths, lifecycle |
| `references/packets.md` | wire format, the three notations (the `b` clash), source trust levels, the 5-step verification, chat/room/avatar packets, `Users`/`UserUpdate` live layouts, value tables |
| `references/gpython.md` | G-Python API, threading model, proven architecture, traps and fixes, minimal example |
| `references/client-ui.md` | showing bubbles, popups and other windows in the client: what's possible, live results with screenshots, images, rules |
| `references/bugs-and-workarounds.md` | any symptom: triage tree + ~45 real failures with causes and fixes |
| `references/testing-and-release.md` | test layers, fixtures, fake_gearth usage, live checklist, CI, SemVer, update delivery |
| `references/extension-store.md` | publishing: rules, folder, every `extension.json` field, Python packaging, PR flow |
| `references/frameworks.md` | choosing G-Python vs Java vs G-Node vs xabbo vs G-Rust |
| `references/prompts.md` | ready-to-paste developer prompts; runtime system prompts for LLM chat features |
| `references/repos.md` | links (checked), source files worth reading, the worked example |
| `assets/gpython-template/` | the project template (protocol, guard, outbox, hotelui, app, installer, tests) |

## Definition of done (extension change)

- [ ] Names only; every used name checked on connect
- [ ] Callbacks guarded, fast (fake_gearth shows no SLOW), no sends from callbacks
- [ ] Parsers: UTF-8, bounds-checked, live + documented variants, fixture tests
- [ ] Sends paced; flood control honoured; queues bounded
- [ ] Exits on socket close; state rebuilt on reconnect
- [ ] `uv run pytest`, ruff check + format clean
- [ ] README: install/update steps, restart G-Earth then the client, Developer mode note,
      ToS warning and "Unofficial fan project, not affiliated with or endorsed by Sulake Oy."
- [ ] No secrets, personal config, logs or un-anonymised captures committed

## Public text conventions

Plain wording, no marketing tone; keep the disclaimer "Unofficial fan project, not
affiliated with or endorsed by Sulake Oy." in READMEs; never commit or print env files
with secrets; ask before committing or pushing on someone's behalf.

## Versioning of this skill

V1 (1.1.0, 2026-10-19). Changes are logged in `CHANGELOG.md`. When a fact here is
contradicted by a live capture or newer source, the capture wins: fix the reference,
note the build and date, and bump the version.
