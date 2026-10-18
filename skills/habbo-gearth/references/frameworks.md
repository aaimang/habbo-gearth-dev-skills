# Choosing a framework

All frameworks speak the same G-Earth extension protocol (gearth-runtime.md section 3),
so packet knowledge carries over. Store names and languages are from
G-ExtensionStore `store/config.json` (2026-10-18).

| Store framework name | Language | Repo | Install for users | Notes |
|---|---|---|---|---|
| `Native` | Java | G-Earth's own `G-Earth-Api` (https://github.com/G-Realm/G-Earth), templates https://github.com/sirjonasxx/G-Earth-template-extensions | none (needs Java) | Most store extensions; JavaFX UI possible; most complete API |
| `G-Python` | Python | https://github.com/sirjonasxx/G-Python (PyPI `g-python`, pin 0.1.6) | `pip install g-python` | Simple; see gpython.md for its traps; best for bots with Python libraries (LLM SDKs) |
| `G-Node` | Node.js / ts-node | https://github.com/G-Realm/G-Node (was WiredSpast/G-Node) | yes | Popular second choice; JS ecosystem |
| `G-Rust` | Rust | https://github.com/G-Realm/G-Rust (crate `g-rust`, beta, last push 2024-05) | no | Typed parsers in `src/extension/parsers/` are the best layout reference, and HabboPackets is generated from them |
| `Xabbo` | C# | https://github.com/xabbo/gearth (+ `xabbo/core`, `xabbo/common`) | no | Richest game-state model (room, users, furni, inventory); great second source for layouts |
| `GoEarth` | Go | https://github.com/xabbo/goearth | no | xabbo's Go framework; 14 store extensions |
| `Geode` | C#, Visual Basic | listed as LilithRainbows/Geode, **repo gone (404, 2026-10-18)** | yes | .NET 5; don't start new work on it |
| `G-PHP` | PHP | https://github.com/michyaraque/g-php | yes | |
| `QX` | C# scripting | https://github.com/QDaves/QX-Scripter | .NET 10 | scripting environment |

Related tools: **G-Wiredfy** (https://github.com/at15four2020/G-Wiredfy, Node, 2021),
WIRED-like scripting on G-Earth; **xabbo scripter** (https://github.com/xabbo/scripter);
**G-Mem** (RC4 key extractors for Flash, 2022).

## G-Rust in brief

Crate `g-rust` 0.0.1-beta.8 (beta). Shape: `Extension<Globals>::new()`, set
`ext.info.name = ...`, typed intercepts like
`ext.intercept(fn(&mut Extension<G>, &mut HMessage, &mut Users))`, then `ext.run()`.
Examples in the repo: `basic-extension`, `chat-logger` (room index -> name from `Users` /
`UserRemove`), `clear-wired-selection`. Worth reading for layouts even if you never
write Rust.

## Decision guide

| Situation | Pick |
|---|---|
| Bot that calls an LLM / web APIs, quick iteration, user installs from GitHub | **G-Python** (with the template) |
| Public store extension with a UI, many users, no setup | **Native** (Java/JavaFX) or **G-Node** |
| Heavy game-state logic (furni, inventory, trading) | **Xabbo** (C#) or GoEarth |
| You need to *read* how a packet is parsed | G-Rust source / HabboPackets, then xabbo |
| Room variables / scores that must persist and be official | not an extension: the **WIRED Web API** (`habbo-wired-api` skill) |
