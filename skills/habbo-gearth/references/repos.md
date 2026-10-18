# Links and sources (checked 2026-10-18)

Every GitHub URL below returned HTTP 200 on 2026-10-18 unless marked. Read code with
`curl -s https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`; list files
with `https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1` (anonymous
limit 60 requests/hour; parse with `json.loads(text, strict=False)`). `gh` may not be
installed.

## Packet data

| What | Link | Notes |
|---|---|---|
| HabboPackets (site) | https://laande.github.io/HabboPackets/ | browsable list, field names, structures |
| HabboPackets JSON | `https://laande.github.io/HabboPackets/api/{packets,fields,templates}.json` | used by `scripts/habbo_packets.py` (cached 7 days) |
| HabboPackets repo | https://github.com/Laande/HabboPackets | `scripts/generate.js` builds the JSON from G-Rust's Rust structs; last push 2026-09 |
| Sulek | `https://api.sulek.dev/releases/<hotelVersion>/messages` | names + ids per exact client build (what G-Earth uses); `/releases` lists builds |
| G-Rust parsers | https://github.com/G-Realm/G-Rust `src/extension/parsers/{incoming,outgoing,subparsers}.rs` | the source of HabboPackets; `src/protocol/vars/legacy.rs` explains LegacyId/LegacyDouble |
| xabbo core | https://github.com/xabbo/core | independent C# parsers and game state |
| Nitro renderer | https://github.com/billsonnn/nitro-renderer | HTML5 client parsers (`FloodControlParser`, `RoomUnitChatParser`, 100-char limit) |

## G-Earth

| Repo / file | Why read it |
|---|---|
| https://github.com/G-Realm/G-Earth (branch `moon`) | maintained G-Earth |
| `G-Earth/src/main/java/gearth/app/protocol/HConnection.java` | `canSendPacket`: packet safety + Developer mode |
| `.../protocol/connection/packetsafety/{PacketSafetyManager,SafePacketsContainer}.java` | "seen" headers per hotel version |
| `.../services/extension_handler/ExtensionHandler.java` | unsafe sends dropped + logged |
| `.../extensions/implementations/network/NetworkExtensionCodec.java` | extension message types, Latin-1 transport |
| `.../network/executer/ExecutionInfo.java` | `Extensions/` location (`gearth.data.dir`), Install-button file types |
| `.../network/executer/NormalExtensionRunner.java`, `.../extensionstore/` | how folders and the store are run; why `.DS_Store` crashes |
| `.../services/packet_info/providers/implementations/SulekPacketInfoProvider.java` | Sulek fetch, suffix stripping |
| `G-Earth-Api/src/main/java/gearth/protocol/connection/HClient.java` | client types `UNITY FLASH NITRO SHOCKWAVE` |
| `G-Earth-Api/.../services/packet_representation/PacketStringUtils.java` | expression syntax |
| https://github.com/sirjonasxx/G-Earth | original repo (older links) |
| https://github.com/sirjonasxx/G-Earth-template-extensions | Java extension templates (2021) |
| https://github.com/sirjonasxx/G-Mem | RC4 key extractors for Flash (2022) |

## Frameworks

| Repo | Language |
|---|---|
| https://github.com/sirjonasxx/G-Python + https://pypi.org/project/g-python/0.1.6/ | Python (pin 0.1.6) |
| https://github.com/G-Realm/G-Node | Node.js |
| https://github.com/G-Realm/G-Rust | Rust (beta) |
| https://github.com/xabbo/gearth, https://github.com/xabbo/common | C# |
| https://github.com/xabbo/goearth | Go |
| https://github.com/michyaraque/g-php | PHP |
| https://github.com/QDaves/QX-Scripter | C# scripting |
| LilithRainbows/Geode | C# (**404 on 2026-10-18**) |
| https://github.com/at15four2020/G-Wiredfy | WIRED-like scripting (Node, 2021) |
| https://github.com/xabbo/scripter | xabbo scripter |

## Store

| What | Link |
|---|---|
| G-ExtensionStore | https://github.com/sirjonasxx/G-ExtensionStore (branch `repo/1.5.3`) |
| rules / format | README.md |
| categories, frameworks | `store/config.json` |
| CI checks | `scripts/tests/extensions/{extension_config,store}.test.js` |
| every published entry | `.auto-generated/extensions.json` |

## Worked example

`assets/gpython-template/` in this skill: a complete, tested G-Python extension
(protocol, guard, outbox, app, installer, tests). Create a copy with `scripts/scaffold.py`.

## Related skill

- `habbo-wired-api` (`~/.claude/skills/habbo-wired-api/`): the official WIRED Web API (room
  variables over REST). Use it instead of an extension whenever persistent room state is
  the goal.
