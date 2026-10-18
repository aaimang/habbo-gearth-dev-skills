# habbo-gearth-dev-skills

Agent skills for building tools for the hotel game: G-Earth extensions, packet work,
G-Python, and the official WIRED Web API. Written for Claude Code (they're plain
`SKILL.md` folders, so any agent that reads skills can use them).

> Unofficial fan project, not affiliated with or endorsed by Sulake Oy.
> G-Earth sits between the game client and the hotel; using it breaks the game's Terms
> of Service. Prefer the official Web API where it can do the job.

## Skills

| Skill | Version | What it covers |
|---|---|---|
| [`habbo-gearth`](skills/habbo-gearth/) | 1.0.1 | G-Earth extensions end to end: the extension protocol, packet names vs ids (Sulek), HabboPackets layouts and how the live client differs from them, packet safety, G-Python threading rules, installing, the macOS `.DS_Store` crash, publishing to G-ExtensionStore. Comes with a tested G-Python project template and scripts to look up and decode packets, fake G-Earth for tests, scaffold projects and validate store entries |
| [`habbo-wired-api`](skills/habbo-wired-api/) | 1.0.0 | The official WIRED Web API: room variables over REST, read/write keys, profiles, batch, bulk delete, Level Up maths, furni id conversion, 64-bit values, rate limits. Includes the API spec notes, wrapper notes and helper scripts |

## Install (Claude Code)

Clone, then link each skill into your skills folder so updates arrive with `git pull`:

```bash
git clone https://github.com/aaimang/habbo-gearth-dev-skills.git
cd habbo-gearth-dev-skills
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/habbo-gearth" ~/.claude/skills/habbo-gearth
ln -s "$PWD/skills/habbo-wired-api" ~/.claude/skills/habbo-wired-api
```

On Windows, copy the folders into `%USERPROFILE%\.claude\skills\` instead.
For a single project, put them in that project's `.claude/skills/`.

Claude picks a skill when a request matches its description (for example "my G-Earth
extension's packet doesn't parse" or "read a room variable with the Web API").

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
3. Run `python3 scripts/validate_skills.py` (CI runs it too, plus the template on
   Linux, macOS and Windows).
4. Never commit keys, env files, logs, or packet captures with other players' names.

## Sources

Built from the sources each skill lists in its `references/repos.md`, including
[G-Earth](https://github.com/G-Realm/G-Earth), [G-Python](https://github.com/sirjonasxx/G-Python),
[G-Rust](https://github.com/G-Realm/G-Rust), [HabboPackets](https://github.com/Laande/HabboPackets),
[G-ExtensionStore](https://github.com/sirjonasxx/G-ExtensionStore) and the official Web API docs,
plus lessons from running a G-Python extension against the live client.

## License

[MIT](LICENSE). Linked projects keep their own licenses.
