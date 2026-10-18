# Publishing to G-ExtensionStore

Source: https://github.com/sirjonasxx/G-ExtensionStore (default branch `repo/1.5.3`, which
tracks the latest G-Earth), its README, `store/config.json` and its CI tests
(`scripts/tests/**`), read 2026-10-18. The store is built into G-Earth 1.5+ (Store tab),
syncs with Discord for ratings, and lists ~105 extensions (Native/Java 44, G-Node 20,
GoEarth 14, Xabbo 14, G-Python 9, Geode 2, G-Rust 1, QX 1; clients: Flash 89, Origins 17,
Unity 11, Nitro 6).

Run `scripts/validate_store_entry.py "<folder>" --first-submission` before opening the PR:
it mirrors the CI checks below.

## Contents
1. Acceptance rules (review)
2. Folder layout
3. `extension.json` field by field
4. Packaging a Python extension
5. Submit, update, retire
6. Pre-PR checklist

## 1. Acceptance rules

Extension requirements (reviewed by the maintainer; all extensions are free):
- Compatible with the **latest G-Earth** at submission time.
- **Not obfuscated**, and **open source** (exceptions only by contacting the maintainer).
- **No hardcoded header ids.** Use packet names/hashes; runtime detection is allowed;
  asking the user for ids only as a last resort.
- **Not malicious and not aimed at disturbing the game**, including direct advantages
  in games or competitions.

Framework requirements (for G-Earth to treat it as installed):
- Passes `cookie` and `filename` to G-Earth on init (from the CLI args) and connects
  using the `port` arg.
- **The process ends when the socket with G-Earth closes.**
- The framework is listed in `store/config.json` -> `frameworks`.

## 2. Folder layout

```
store/extensions/<Title>/        folder name == title (exactly)
├─ extension.zip     required: everything needed to run, commands run from its root
├─ extension.json    required
├─ icon.png          required: PNG, 20-80 px each side, shown at 40x40
└─ screenshot.png    optional: PNG, 128-960 px wide, 64-1200 px tall
```

No other files are allowed in the folder (CI fails).

## 3. `extension.json`

```json
{
  "title": "Room Helper",
  "description": "What it does.\n\nHow to use it. Limited *styling* is allowed.",
  "authors": [
    { "name": "yourname", "hotel": ".com", "username": "InGameName", "discord": "yourname", "twitter": null }
  ],
  "version": "1.0.0",
  "categories": ["Usability"],
  "source": "https://github.com/you/room-helper",
  "readme": "https://github.com/you/room-helper#readme",
  "releases": "https://github.com/you/room-helper/releases",
  "stable": true,
  "framework": { "name": "G-Python", "version": "0.1.6" },
  "language": "Python",
  "commands": {
    "default": ["python", "main.py", "-c", "{cookie}", "-p", "{port}", "-f", "{filename}"],
    "mac": ["python3", "main.py", "-c", "{cookie}", "-p", "{port}", "-f", "{filename}"]
  },
  "compatibility": { "systems": ["Linux", "Windows", "Mac"], "clients": ["Flash"] },
  "submissionDate": "18-10-2026 12:00:00",
  "updateDate": "18-10-2026 12:00:00",
  "isOutdated": false
}
```

| Field | Rule (CI unless noted) |
|---|---|
| `title` | unique (case-insensitive), **> 4 characters, no `.` or `_`**, valid as a folder name |
| `description` | string; may be long; limited styling |
| `authors[]` | at least one; `name` required; optional `hotel` in `.com .com.br .de .nl .es .fi .fr .it .com.tr`; `discord`, `username`, `twitter` strings |
| `version` | digits and dots only (`1.0.0`, not `v1.0.0`) |
| `categories` | >= 1 of: `Fun`, `Games`, `Trading`, `Building`, `Moderation`, `Usability`, `G-Earth Utilities`, `Others` |
| `source` | URL of the git repo (required) |
| `readme`, `releases` | URL, empty or null |
| `stable` | boolean; **must be `true` in the first PR** (review rule); set `false` later if it breaks and no fix is coming |
| `framework.name` -> `language` | `Native`->Java, `G-Python`->Python, `Geode`->C#/Visual Basic, `G-Node`->Node.js/ts-node, `G-Rust`->Rust, `Xabbo`->C#, `GoEarth`->Go, `G-PHP`->PHP, `QX`->C# |
| `framework.version` | framework version you built with (for `Native`, the G-Earth version) |
| `commands.default` (+ optional `linux`/`windows`/`mac`) | argv run from the unzipped `extension.zip`; must contain `{cookie}`, `{port}`, `{filename}` |
| `compatibility.systems` | non-empty subset of `Linux`, `Windows`, `Mac` |
| `compatibility.clients` | non-empty subset of `Unity`, `Flash`, `Nitro`, `Origins` (not compatible out of the box: test each) |
| `submissionDate`, `updateDate` | `DD-MM-YYYY HH:MM:SS`; not in the future; `updateDate >= submissionDate`; on updates `submissionDate` must stay the same and `updateDate` can't go backwards |
| `isOutdated` | boolean; `true` retires the extension |

## 4. Packaging a Python extension

The store runs `commands` with the **system** interpreter in the unzipped folder; there's
no virtualenv and no `uv`. The G-Python framework entry says installation is required:
users must `pip install g-python` themselves. Consequences:

- Ship plain `.py` files (no compiled wheels), with the entry script at the zip root
  (`main.py`), and **only depend on `g-python`** (vendor small pure-Python helpers into the
  zip, or the extension fails on machines without them).
- `python` doesn't exist on many Macs; add a `"mac"` command with `python3`.
  `validate_store_entry.py` warns about this.
- Pinning: say "requires `pip install g-python==0.1.6`" in the description/readme.
- Don't put `.env`, API keys, personal config or logs in the zip (the validator errors).
- Bundle-layout option used by one store extension (G-Loader): a Java launcher
  (`PyExtensionSetup.jar`) that sets up Python; heavier, rarely worth it.
- If the extension needs third-party packages (e.g. an LLM SDK) or secrets, the store is
  a poor fit: distribute from GitHub with the folder + `command.txt` installer instead
  (gearth-runtime.md section 8).

Make the zip from a clean export so nothing stray gets in:

```bash
git archive --format=zip -o extension.zip HEAD:src/my_ext   # files at the zip root
unzip -l extension.zip
```

## 5. Submit, update, retire

- **Submit:** fork, add `store/extensions/<Title>/` with the files, open a PR into the
  base branch (`repo/<latest G-Earth>`). CI (Jest) runs the checks; the maintainer reviews
  the code.
- **Update:** same PR flow. Any change to `extension.zip`, or to `commands`, **requires a
  new `version`** (and a newer `updateDate`). Description or screenshot changes can keep
  the version.
- **Retire:** PR setting `"isOutdated": true`.
- After merge, G-Earth's Store tab shows it; installs unzip into
  `Extensions/<Title>_<version>/extension/`.

## 6. Pre-PR checklist

- [ ] Uses names only (no `HPacket(1234, ...)`, no `{h:1234}`), no obfuscation, public repo
- [ ] Exits when G-Earth closes the socket (`fake_gearth.py --run ...` prints "exited")
- [ ] Every intercept answered fast (`fake_gearth.py` shows no SLOW lines)
- [ ] Tested on each OS and client listed in `compatibility`
- [ ] Doesn't give a competitive or game advantage, doesn't spam or disturb rooms
- [ ] `validate_store_entry.py "<folder>" --first-submission` -> 0 errors
- [ ] README states the ToS risk and the unofficial-fan-project disclaimer
