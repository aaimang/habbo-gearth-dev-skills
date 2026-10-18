# habbo-gearth-dev-skills

Agent skills for building tools for the hotel game: G-Earth extensions, packet work,
G-Python, and the official WIRED Web API. They follow the open
[Agent Skills](https://agentskills.io) format (a folder with a `SKILL.md`), so they work
in Claude Code, Codex, Gemini CLI, Cursor and any other agent that supports it.

> Unofficial fan project, not affiliated with or endorsed by Sulake Oy.
> G-Earth sits between the game client and the hotel; using it breaks the game's Terms
> of Service. Prefer the official Web API where it can do the job.

## Skills

| Skill | Version | What it covers |
|---|---|---|
| [`habbo-gearth`](skills/habbo-gearth/) | 1.1.0 | G-Earth extensions end to end: the extension protocol, packet names vs ids (Sulek), HabboPackets layouts and how the live client differs from them, packet safety, G-Python threading rules, showing bubbles and popups inside the client, installing, the macOS `.DS_Store` crash, publishing to G-ExtensionStore. Comes with a tested G-Python project template and scripts to look up and decode packets, fake G-Earth for tests, scaffold projects and validate store entries |
| [`habbo-wired-api`](skills/habbo-wired-api/) | 1.0.1 | The official WIRED Web API: room variables over REST, read/write keys, profiles, batch, bulk delete, Level Up maths, furni id conversion, 64-bit values, rate limits. Includes the API spec notes, wrapper notes and helper scripts |

## Install

```bash
git clone https://github.com/aaimang/habbo-gearth-dev-skills.git
cd habbo-gearth-dev-skills
python3 scripts/install_skills.py
```

That links both skills into `~/.agents/skills` and `~/.claude/skills`, which covers:

| Agent | Reads skills from |
|---|---|
| Codex | `~/.agents/skills`, or `.agents/skills` in a repo |
| Gemini CLI | `~/.agents/skills` (alias of `~/.gemini/skills`), or `.agents/skills` in a workspace |
| Cursor | `~/.agents/skills`, `~/.cursor/skills`, and the Claude / Codex folders |
| Claude Code | `~/.claude/skills`, or `.claude/skills` in a project |

Links mean a `git pull` updates every agent at once. Options:

- One agent only: `--target agents` (Codex, Gemini CLI, Cursor) or `--target claude`.
- One project only: `--dest path/to/project/.agents/skills` (or `.claude/skills`).
- Windows without symlink rights: add `--copy` (re-run after each `git pull`).
- Remove: `--uninstall`. Preview anything with `--dry-run`.

Or copy the folders in `skills/` by hand to any of the paths above. Restart the agent
(or start a new session) afterwards. It picks a skill when a request matches the
skill's description, for example "my G-Earth extension's packet doesn't parse" or "read
a room variable with the Web API"; you can also ask for it by name.

## Requirements

- Python 3.9+ for the scripts below (standard library only).
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for G-Python extension development: the `habbo-gearth` template and its
  workflows use `uv sync` and `uv run`.

## Tools you can run directly

All are standard-library Python 3.9+.

```bash
python3 skills/habbo-gearth/scripts/habbo_packets.py show Chat
python3 skills/habbo-gearth/scripts/habbo_packets.py decode --file Users.hex --layout "i[i s s s i i i s i i s i i s s i b i]"
python3 skills/habbo-gearth/scripts/scaffold.py --title "Room Helper" --dest ~/code/room-helper
python3 skills/habbo-gearth/scripts/fake_gearth.py --run "<command with {port}>" --intercept '{out:Chat}{s:"!ping"}{i:0}{i:-1}'
python3 skills/habbo-gearth/scripts/validate_store_entry.py "store/extensions/My Extension"
python3 skills/habbo-wired-api/scripts/furni_ids.py
```

## Contributing

1. Edit a skill; keep `SKILL.md` under 500 lines and put detail in `references/`.
2. If a live capture or newer source contradicts a reference, fix it, note the client
   build and date, and bump the skill's `metadata.version` and `CHANGELOG.md`.
3. Keep skills agent-neutral: no agent-specific paths or tool names in `SKILL.md`, and
   frontmatter limited to the [spec](https://agentskills.io/specification) fields.
4. Run `python3 scripts/validate_skills.py` (CI runs it too, plus the template on
   Linux, macOS and Windows).
5. Never commit keys, env files, logs, or packet captures with other players' names.

## Sources

Built from the sources each skill lists in its `references/repos.md`, including
[G-Earth](https://github.com/G-Realm/G-Earth), [G-Python](https://github.com/sirjonasxx/G-Python),
[G-Rust](https://github.com/G-Realm/G-Rust), [HabboPackets](https://github.com/Laande/HabboPackets),
[G-ExtensionStore](https://github.com/sirjonasxx/G-ExtensionStore) and the official Web API docs,
plus lessons from running a G-Python extension against the live client.

## License

[MIT](LICENSE). Linked projects keep their own licenses.
