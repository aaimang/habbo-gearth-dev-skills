# G-Earth runtime: how extensions are found, started, connected and allowed to send

Verified against G-Realm/G-Earth source (branch `moon`, 1.5.4+), G-Python 0.1.6 and a
live macOS install (2026-10). Where something is from docs only, it says so.

## Contents
1. What G-Earth is (and the ToS line)
2. Clients and hotels
3. The extension protocol (socket, message types, framing)
4. Where extensions live and how they're launched
5. Packet names: Sulek and the catalogue
6. Packet safety and Developer mode
7. Expressions, the logger and the injection tab
8. Install paths compared
9. Lifecycle rules that bite

## 1. What G-Earth is

G-Earth is a Java (JavaFX) packet proxy: the game client connects to G-Earth, G-Earth
connects to the hotel, and every packet passes through it. Extensions are separate
processes that G-Earth talks to over a local TCP socket; they can read, block, edit and
inject packets.

**ToS:** this is a man-in-the-middle on the game connection and breaks Habbo's Terms of
Service (sections 5 and 8). Say so in READMEs and when advising users. If the job can be
done with the official WIRED Web API (room variables over REST), use that instead (see
the `habbo-wired-api` skill). Public text for these projects: "Unofficial fan project,
not affiliated with or endorsed by Sulake Oy."

| Repo | Status |
|---|---|
| https://github.com/G-Realm/G-Earth (branch `moon`) | maintained; use this |
| https://github.com/sirjonasxx/G-Earth | original; README points to G-Realm; same extension protocol |

## 2. Clients and hotels

| G-Earth client type | What it is | Notes |
|---|---|---|
| `FLASH` | the official **AIR desktop client** (Habbo Launcher) and the old Flash client | Most extensions target this. Ids differ between Windows and macOS builds |
| `UNITY` | old Unity client | Windows only in G-Earth; store compatibility value `Unity` |
| `NITRO` | HTML5 client (retros) | `Nitro` in the store |
| `SHOCKWAVE` | Habbo Origins | `Origins` in the store; different protocol (G-Earth uses its own mapping) |

- `connection_info["client_type"]` (G-Python) tells you which one connected. Check it on
  `connection_start` and warn if your extension only supports one.
- macOS: G-Earth re-signs the AIR client from
  `~/Library/Application Support/Habbo Launcher/downloads/air/<version>/Habbo.app`.
- Hotel version (e.g. `MAC63-202610131318-613990583`) is in `connection_info["hotel_version"]`;
  it keys the Sulek catalogue and G-Earth's packet-safety memory.

## 3. The extension protocol

Extensions connect to `127.0.0.1:<port>` (G-Earth's default 9092; it counts up to the next
free port, and the Extensions tab shows the real one). Every message in both directions
is framed like a Habbo packet: `int32 length` (bytes after this field), `uint16 type`,
payload. Strings are `u16 length + bytes`; packets inside messages travel as Latin-1
text, which keeps every byte intact.

| G-Earth -> extension | Type | Payload |
|---|---|---|
| ON_DOUBLE_CLICK | 1 | none (user pressed ▶; only if the extension asked for it) |
| INFO_REQUEST | 2 | none |
| PACKET_INTERCEPT | 3 | 4-byte-length string: `blocked\tindex\tTOCLIENT\|TOSERVER\t<edited 0/1><raw packet bytes>` |
| FLAGS_CHECK | 4 | `i count, s...` (answer to REQUEST_FLAGS) |
| CONNECTION_START | 5 | `s host, i port, s hotelVersion, s clientIdentifier, s clientType, i n, n x (i headerId, s hash, s name, s structure, B isOutgoing, s source)` |
| CONNECTION_END | 6 | none |
| INIT | 7 | `B awaitConnection` (newer G-Earth): if true, `start()` returns only after CONNECTION_START |
| PACKET_TO_STRING_RESPONSE / STRING_TO_PACKET_RESPONSE | 20 / 21 | expression conversion answers |

| Extension -> G-Earth | Type | Payload |
|---|---|---|
| EXTENSION_INFO | 1 | `s title, s author, s version, s description, B onClick, B hasFile, s file, s cookie, B canLeave, B canDelete` |
| MANIPULATED_PACKET | 2 | the intercept string back (possibly blocked/edited). **Every intercept must be answered.** |
| REQUEST_FLAGS | 3 | none |
| SEND_MESSAGE | 4 | `B toServer, i length, bytes packet` |
| PACKET_TO_STRING_REQUEST / STRING_TO_PACKET_REQUEST | 20 / 21 | expression conversion |
| EXTENSION_CONSOLE_LOG | 98 | `s "[color]Title --> text"` |

Consequences:
- **G-Earth holds each intercepted packet until the extension answers.** A slow callback
  freezes the game; a callback that never returns stalls that packet type for good.
- Without a cookie (`-c`), G-Earth shows an "allow this extension?" prompt; if declined,
  the socket closes. G-Python 0.1.6 then hangs in `start()` (see gpython.md).
- `scripts/fake_gearth.py` implements the G-Earth side of this table for tests.

## 4. Where extensions live and how they're launched

Installed extensions are folders in G-Earth's `Extensions/` directory:

```
Extensions/
├─ My Extension_1.2.0/          <Title>_<version>; G-Earth splits on "_"
│  ├─ command.txt               JSON argv
│  └─ extension/                working directory for the command (store installs unzip here)
└─ .DS_Store/                   macOS only: empty FOLDER guard (see section 9)
```

`command.txt` is a JSON array. G-Earth replaces `{cookie}`, `{port}`, `{filename}` and runs
it with `extension/` as the working directory:

```json
["/abs/path/.venv/bin/python","-m","my_ext","--project-dir","/abs/path","-c","{cookie}","-p","{port}","-f","{filename}"]
["java","-jar","TradeBlocker.jar","-c","{cookie}","-p","{port}","-f","{filename}"]
```

| OS | `Extensions/` location | G-Earth's own log |
|---|---|---|
| macOS | `~/Library/Application Support/G-Earth/Extensions/` (the app launcher sets `-Dgearth.data.dir`) | `~/Library/Logs/G-Earth/app.log` |
| Windows, Linux | next to `G-Earth.exe` / `G-Earth.jar`, wherever it was unzipped (nothing sets `gearth.data.dir`) | console / next to the jar |

- Absolute paths in `command.txt`: apps started by G-Earth don't get your shell's `PATH`
  or environment, so `python`, `uv`, env vars from `.zshrc` are not there. Point at the
  project's virtualenv Python and pass `--project-dir` so the extension finds its config.
- The cookie is single-use. **An extension can't relaunch itself**; after an update the
  user restarts G-Earth.
- The store's "Installed" tab ignores folder names without `_`.

## 5. Packet names: Sulek and the catalogue

- For Flash/AIR, G-Earth downloads names and ids for the **exact client build** from
  Sulek: `https://api.sulek.dev/releases/<hotelVersion>/messages` (JSON
  `{"messages": {"incoming": [...], "outgoing": [...]}}`, each `{id, name, confident}`).
  G-Earth strips `MessageEvent` / `MessageComposer`: `ChatMessageComposer` -> `Chat`.
  (The old Harble provider is offline.)
- The catalogue reaches extensions in CONNECTION_START (G-Python: `ext.packet_infos[direction][name]`).
  Before that, packets can't be built or matched by name.
- Ids differ between Windows and macOS AIR builds and change with client updates; names
  are stable across builds (they're the client's class names). Always use names.
- Look up a name, layout or id: `scripts/habbo_packets.py show|search|id`.

## 6. Packet safety and Developer mode

From `HConnection.canSendPacket` (G-Realm):

```java
return isPacketSendingAllowed(direction, packet) && (developerMode || isPacketSendingSafe(direction, packet));
```

- **Seen means safe.** A header becomes sendable once G-Earth has seen that header go by
  in that direction. Memory is per hotel version, lasts while G-Earth is open, survives
  extension restarts.
- **Unsafe sends are silently dropped** (G-Earth logs "attempted to send an unsafe packet,
  but had no permission"). Nothing reaches the hotel; the extension isn't told.
- **Developer mode** (Extra tab) disables the check. G-Earth warns it can get accounts
  banned; that's about sending wrong ids, which names avoid, but repeat the warning.
- **Expressions don't bypass it**: `{out:Dance}{i:1}` resolves to the same header id.
- Practical guidance for users: turn on Developer mode, or do each action once by hand
  (chat, whisper, shout, walk, dance, sign...) after starting G-Earth.
- Don't keep your own copy of "seen" headers that resets on reconnect: it will block
  sends G-Earth would allow (bugs-and-workarounds 3.2). Send, and let G-Earth decide.
- Since G-Earth 1.5.3, installing extensions the *old* way (Install button) needs
  **Experimental mode** (Extra tab), with a warning. The store is the main path.

## 7. Expressions, the logger and the injection tab

Expressions are G-Earth's text form of a packet:

```
{out:MoveAvatar}{i:5}{i:7}          walk to tile 5,7
{out:Chat}{s:"hello"}{i:0}{i:-1}    say "hello"
{in:Chat}{i:0}{s:"fake"}{i:0}{i:0}{i:0}{i:-1}   only your own client sees it
```

Field codes (G-Earth `PacketStringUtils`): `{i:}` int, `{s:"..."}` string, `{b:N}` byte
or `{b:true}` / `{b:false}` bool, `{u:}` short, `{l:}` long, `{d:}` double, `{f:}` float;
`{h:1234}` picks a header by id instead of `{in:Name}` / `{out:Name}` (avoid: ids change).
HabboPackets and G-Python's `read()` use other letters; see packets.md.

- **Packet logger** (G-Earth's logger window, or the "Packet Info Explorer" extension):
  shows each packet with its name, direction and an expression. Use it to capture a
  live layout before trusting any documented one.
- **Injection tab:** send an expression by hand. Quickest way to test a layout or to
  "teach" G-Earth a header for packet safety.
- From code, `ext.send_to_server("{out:Dance}{i:1}")` asks G-Earth to convert the
  expression (a round trip); `HPacket("Dance", 1)` is local and faster.

## 8. Install paths compared

| Path | How | Good for | Gotchas |
|---|---|---|---|
| **Folder + command.txt** (the template's `scripts/install_gearth.py`) | script writes `Extensions/<Title>_<ver>/command.txt` pointing at the project venv | your own extensions; git + uv workflow; one-click updates | absolute paths; rerun after version bumps; restart G-Earth |
| **G-ExtensionStore** | user installs from G-Earth's Store tab; G-Earth unzips `extension.zip` into `Extensions/<Title>_<ver>/extension/` and writes the command from `extension.json` | sharing publicly | must follow store rules (extension-store.md); Python extensions run with the system `python` and need `g-python` installed globally |
| **Install button** (old way) | G-Earth copies one file into `Extensions/` and runs it by type (`ExecutionInfo`): `.jar` -> `java -jar`, `.py` -> `python`, `.py3` -> `python3` (use on macOS), `.js` -> `node`, `.sh` / `.exe` directly; always adds `-p {port} -f {filename} -c {cookie}` | quick experiments | needs Experimental mode on 1.5.3+; only that single file is copied, so dependencies and helper modules must already be installed |
| **Run by hand** | `python -m my_ext -p 9092` with G-Earth open | development | no cookie, so G-Earth shows the allow prompt; not listed as installed |

## 9. Lifecycle rules that bite

1. **After restarting G-Earth, restart the game client through it.** Otherwise the
   extension connects to G-Earth (INIT) but never gets CONNECTION_START, so it sees no
   packets. Symptom: log shows "connected to G-Earth" but no "Connected to game-..." line.
2. **macOS `.DS_Store`:** G-Earth tries to start *every* entry in `Extensions/`. A
   `.DS_Store` file (Finder writes one whenever the folder is viewed) has no command, so
   JavaFX start-up throws a NullPointerException and G-Earth's window never opens (process
   keeps running; `app.log` ends with "Running extension .../Extensions/.DS_Store").
   Fix: delete the file and create an empty **folder** named `.DS_Store`; Finder can't
   overwrite a folder and G-Earth logs an IOException for it and carries on. Don't tell
   users to open that folder in Finder.
3. **The process must exit when the socket closes** (store requirement; also avoids
   orphaned Pythons). Loop on `ext.is_closed()`.
4. **Disconnect/reconnect:** CONNECTION_END clears `connection_info` and `packet_infos`.
   Drop queued sends, reset per-session state, and rebuild room state on the next
   `connection_start` (you only learn a room's users when entering it).
5. **Room state after an extension restart:** the extension missed the room-entry packets.
   `GetHeightMap` no longer exists in AIR builds, so there's no "resend room" request;
   either ask the user to re-enter, or remember the room id and send
   `GetGuestRoom(roomId, 0, 1)` (same as clicking it in the navigator).
