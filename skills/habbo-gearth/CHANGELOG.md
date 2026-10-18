# Changelog

## 1.1.0, 2026-10-19

- New `references/client-ui.md`: showing UI inside the client from an extension. What
  is not possible (custom windows, patching the client), the incoming packets that are
  (`NotificationDialog`, `MOTDNotification`, `HabboBroadcast`, `InClientLink`), live
  results with redacted screenshots (`assets/client-ui/`), image URLs, and the rules
  from shipping it (owner commands, a notify thread, throttling, name check, console
  fallback). Live-tested on AIR MAC63-202610151745-513993601, 2026-10-19, with
  Developer mode on only.
- `SKILL.md`: workflow G (show something in the client), reference map entry,
  description keywords.
- Template: `hotelui.py` (bubble and popup builders, `escape`, `HotelNotifier` on an
  `ext-notify` thread) with `tests/test_hotelui.py`, and a `!help` command that opens a
  popup. CI's fake G-Earth run now covers `!help`.
- `packets.md` section 12: live-verified `NotificationDialog` and `MOTDNotification`.
- `gpython.md`: `send_to_client`, like `send_to_server`, returns None in g-python 0.1.6
  and never raises; an unknown name only prints to stderr.
- `bugs-and-workarounds.md` 3.8 (raw `<b>` tags) and 3.9 (window never shows).
- `prompts.md` 1.9: prompt for adding in-client windows.

## 1.0.2, 2026-10-18

- Works with any Agent Skills client (Claude Code, Codex, Gemini CLI, Cursor):
  `license: MIT` and a `compatibility` line in the frontmatter, agent-neutral wording
  and paths (no `~/.claude/...`).

## 1.0.1, 2026-10-18

- `fake_gearth.py`: shut the socket down before closing it. On Linux a plain `close()`
  while the reader thread is blocked in `recv()` sends no FIN, so the extension never
  saw G-Earth go away and the exit check failed (seen in CI on ubuntu-latest).

## 1.0.0 (V1), 2026-10-18

First release.

- `SKILL.md`: ground rules (ToS, what not to build, privacy, secrets), mental model,
  golden do/don't rules, workflows A-F, tools, reference map, definition of done.
- References: G-Earth runtime and protocol, packets (wire format, notations, live
  drift, value tables), G-Python, bugs and workarounds (triage tree + catalogue),
  testing and release, G-ExtensionStore, frameworks, prompts, links.
- Scripts (stdlib only):
  - `habbo_packets.py`: HabboPackets lookup, Sulek ids, layout decoder with variants.
    Verified on a real `Users` capture: documented layout leaves 4 bytes, live layout
    decodes all.
  - `fake_gearth.py`: stand-in G-Earth for end-to-end tests. Verified against the
    template extension (handshake, blocking, UTF-8 sends, console, exit on close).
  - `scaffold.py`: new G-Python project from the template. Generated project passes
    16 tests, ruff check and format.
  - `validate_store_entry.py`: G-ExtensionStore CI rules. Verified on a real published
    entry (MultiWhisper: 0 errors).
- Template: `assets/gpython-template/` (protocol, guard, outbox, app, installer, tests).

Verified against: G-Earth 1.5.4 (G-Realm `moon`), g-python 0.1.6, Habbo AIR MAC63
2026-10 builds, HabboPackets (generated 2026-09), G-ExtensionStore `repo/1.5.3`.
