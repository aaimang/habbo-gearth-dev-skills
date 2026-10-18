# Changelog

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
