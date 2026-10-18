# Testing, CI, versioning and release for G-Earth extensions

## Contents
1. Test pyramid
2. Offline unit tests (packets from bytes)
3. Fixtures from live captures
4. End-to-end without Habbo: fake_gearth.py
5. Live test checklist (real client)
6. CI matrix
7. Versioning and release
8. Update delivery

## 1. Test pyramid

| Layer | Tool | Catches |
|---|---|---|
| Parsers and builders | pytest + `HPacket(header, ...)` / `HPacket.from_bytes` | layout and encoding bugs, truncation |
| Behaviour | pytest + a fake `Extension` (records intercepts, sends, console) and a fake outbox | blocking, gating, queueing, notices |
| Threads | real `Outbox` with tiny intervals | ordering, pacing, pauses, shutdown |
| Protocol end to end | `scripts/fake_gearth.py --run ...` | handshake, intercept answer time, real sends, exit on close |
| Live | the real client, a test room, an alt account | packet safety, drift, UX |

The template (`assets/gpython-template/tests/`) has the first three layers.

## 2. Offline unit tests

```python
from my_ext.gpython import HPacket

def packet(*fields, header=1):
    pkt = HPacket(header, *fields)   # numeric header: names need a live catalogue
    pkt.read_index = 6
    return pkt

def test_incoming_chat_utf8():
    chat = parse_incoming_chat(ChatMode.CHAT, packet(7, "héllo 👋", 0, 2, 0, -1))
    assert chat.text == "héllo 👋"

def test_truncated():
    with pytest.raises(ProtocolError):
        parse_incoming_chat(ChatMode.CHAT, HPacket.from_bytes(bytes.fromhex("000000080001000000070009 6162")))
```

- `HPacket("Chat", ...)` keeps `incomplete_identifier == "Chat"` until sent; assert on that
  to check builders use names.
- Cover: UTF-8 (accents, emoji), truncation at every field, empty lists, max-size lists,
  negative ints (-1 tails), each entity type in `Users`.

## 3. Fixtures from live captures

1. Let the guard save the first bad packet (`logs/bad-packets/*.hex`) or copy hex from the
   G-Earth logger.
2. **Anonymise** names, mottos and figures before committing (they're other players'
   data): replace strings with same-length placeholders so lengths still line up, or
   rebuild the packet with the builder helpers.
3. Paste as a constant (`LIVE_USERS_PLAYER = bytes.fromhex("...")`) with a comment: build,
   date, what it proves.
4. Test both: the live layout parses it fully; the documented layout alone does not.

## 4. End-to-end without Habbo

```bash
python3 ~/.claude/skills/habbo-gearth/scripts/fake_gearth.py \
  --run "$PWD/.venv/bin/python -m my_ext -p {port} -c TEST -f test --project-dir $PWD" \
  --intercept '{out:Chat}{s:"!ping"}{i:0}{i:-1}' \
  --intercept '{out:Chat}{s:"hello"}{i:0}{i:-1}' \
  --intercept '{in:FloodControl}{i:3}' --double-click
```

It prints the extension's info, each intercept's result (BLOCKED / passed / edited and
how many ms it took; SLOW above 50 ms), every packet the extension sent (decoded name +
hex), console lines, and whether the process exited after the socket closed. Exit code 0
= all good. Add `--packet out:Name=ID` for names outside the default chat set.

## 5. Live test checklist

- [ ] G-Earth started, then the client through it; extension shows the game connection
- [ ] Without Developer mode: first send of each type dropped until done by hand
      (expected); notice tells the user
- [ ] With Developer mode: every feature works first time
- [ ] Room with 20+ users: no bad-packet warnings; if any, decode the saved file
- [ ] Accents and emoji in names and chat
- [ ] Flood control: spam test on an alt, outbox pauses
- [ ] Extension restart mid-session: state recovers (rejoin or notice)
- [ ] G-Earth restart: extension exits; after restarting the client it reconnects
- [ ] Windows and macOS if both are claimed (ids and paths differ)

## 6. CI matrix

GitHub Actions, `ubuntu-latest`, `windows-latest`, `macos-latest`, with uv:

```yaml
- uses: astral-sh/setup-uv@v6
- run: uv sync --all-groups
- run: uv run ruff check . && uv run ruff format --check .
- run: uv run pytest -q
```

- Run tests on branch pushes and PRs, not on tag pushes (avoids duplicate runs).
- Tk-dependent tests must `importorskip` (runner Pythons often lack Tkinter).
- Docs (Sphinx/MyST) built clean into a fresh dir with `-E -W --keep-going -n`.

## 7. Versioning and release

- SemVer: PATCH = fixes/docs, MINOR = features or new config options (old configs keep
  working), MAJOR = config-breaking changes.
- One version source per place that shows it: `pyproject.toml`, `__init__.__version__`
  (G-Earth's list shows it; the folder name is `<Title>_<version>`), README, changelog.
  Run `uv lock` after bumping.
- Rerun the installer after a bump so G-Earth's folder matches.
- Release: build on a `dev` branch/worktree, lint + tests + docs clean, fast-forward
  `main`, annotated tag `vX.Y.Z`, push `main`, `dev` and the tag, wait for CI, then
  publish/move the GitHub Release.

## 8. Update delivery

| Distribution | Update path |
|---|---|
| GitHub + `command.txt` installer | in-app check of `GET /repos/{owner}/{repo}/releases/latest` at most daily (anonymous: 60/h/IP), banner, optional one-click update: fetch tags, verify the tag (bugs-and-workarounds 7.3), fast-forward to it, `uv sync` only if `uv.lock` changed, rerun the installer, ask the user to restart G-Earth |
| G-ExtensionStore | bump `version` + `updateDate`, new `extension.zip`, PR; G-Earth shows the update in the Store tab |

Refuse automatic updates for dirty checkouts, non-`main` branches, diverged history and
MAJOR bumps; show manual steps instead.
