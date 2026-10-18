# __TITLE__

__DESC__

A G-Earth extension written with [G-Python](https://github.com/sirjonasxx/G-Python).

> Unofficial fan project, not affiliated with or endorsed by Sulake Oy. G-Earth sits
> between the game client and the hotel; using it is against Habbo's Terms of Service.
> Use at your own risk.

## Requirements

- [G-Earth](https://github.com/G-Realm/G-Earth) 1.5.4 or newer
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (required: it creates the `.venv` that G-Earth runs and installs the pinned
  dependencies)

## Install

```bash
uv sync
uv run python scripts/install_gearth.py
```

On Windows and Linux, add `--gearth-dir "<folder with G-Earth.exe or G-Earth.jar>"`.

Then restart G-Earth, and start the Habbo client through G-Earth again.
"__TITLE__" appears in G-Earth's Extensions tab.

## Use

| Type in chat | What happens |
|---|---|
| `!ping` | Nobody sees it; G-Earth's console answers "pong" |
| `!say hello` | Nobody sees `!say`; you say "hello" |
| `!help` | Nobody sees it; a popup with the commands opens in your client (only you see it) |

If sending does nothing, turn on **Developer mode** in G-Earth's Extra tab, or do the
action once by hand: G-Earth only lets extensions send packet types it has seen. The
`!help` popup needs Developer mode on; without it the commands show in G-Earth's
console instead.

## Update

```bash
git pull
uv sync
uv run python scripts/install_gearth.py
```

Then restart G-Earth and the client.

## Develop

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python scripts/install_gearth.py --dry-run
```

Logs: `logs/__PKG__.log`. Packets that don't parse are saved to `logs/bad-packets/`.
