# Habbo packets: wire format, notations, sources, and the packets bots actually use

For the Habbo **AIR client** (G-Earth `FLASH`) unless noted. Ids shown are from build
`MAC63-202610131318-613990583` (macOS) for orientation only: **code uses names**.

## Contents
1. Wire format
2. Three notations (and the letter clash that causes bugs)
3. Where layouts come from, and how far to trust them
4. Verifying a layout: the 5-step method
5. Chat packets
6. Room and user packets
7. `Users` entry layout (with live drift)
8. `UserUpdate` and its status string (with live drift)
9. Avatar action packets and value tables
10. Tiles, floor map, doors, directions
11. Other packets worth knowing

## 1. Wire format

```
┌────────────┬──────────┬─────────────────────────┐
│ length (4) │ id (2)   │ payload                 │   big-endian throughout
└────────────┴──────────┴─────────────────────────┘
  int32: bytes after this field; uint16 header id; fields back to back, no names
```

Payload starts at **byte 6**. Field encodings: int32 (4), string (u16 length + UTF-8
bytes), bool (1 byte 0/1), short (2), long (8), byte (1). Lists are an int count followed
by the items. Decimal values (tile height z) are **strings** like `"0.15"` on AIR
(G-Rust's `LegacyDouble`). Ids that are ints on Flash/AIR may be longs on Unity
(G-Rust's `LegacyId`).

Misread one field and everything after it is garbage. Absurd values (a string length
bigger than the packet, a coordinate in the millions, a direction above 7) mean you're
out of step: the previous field was wrong or missing.

## 2. Three notations

| Meaning | HabboPackets / G-Rust layouts | G-Python `HPacket.read("...")` | G-Earth expressions |
|---|---|---|---|
| int32 | `i` | `i` | `{i:1}` |
| string (u16 + UTF-8) | `s` | `s` (**decodes Latin-1!**) | `{s:"x"}` |
| bool | **`b`** | **`B`** | `{b:true}` |
| byte | **`c`** | **`b`** | `{b:7}` |
| short | `h` | `u` | `{u:1}` |
| long | `d` | `l` | `{l:1}` |
| float / double | `f` / `g` | (none) | `{f:}` / `{d:}` |
| u32-length string | `S` | `read_string(head=4)` | |

**`b` means bool in HabboPackets but byte in G-Python.** Translate every layout before
using it with `read()`, or better, read field by field with a bounds-checked reader.

HabboPackets extras: `i[ ... ]` counted list, `#N[ ... ]` fixed array of N, `<Name>` shared
structure (see `habbo_packets.py template Name`), `x?` optional (may be absent at the end),
`( a | b )` one of several variants, `·` an empty variant.

## 3. Where layouts come from, and how far to trust them

| Source | What it gives | Trust |
|---|---|---|
| **HabboPackets** (https://laande.github.io/HabboPackets/, repo Laande/HabboPackets) | 461 incoming + 457 outgoing packets, 156 shared structures, field names and types, as JSON: `api/packets.json` (layouts), `api/fields.json` (fields), `api/templates.json` (structures) | Generated from **G-Rust's parsers** (G-Rust last pushed 2024-05), so it lags the live client. Entries marked `custom`/`layoutIsEstimate` are hand-written parsers in G-Rust: the layout is a guess |
| **Sulek** (`api.sulek.dev/releases/<build>/messages`) | names and ids for one exact build; what G-Earth uses | Authoritative for names/ids; no layouts |
| G-Rust `src/extension/parsers/{incoming,outgoing,subparsers}.rs` | the source HabboPackets is generated from; readable Rust structs | as above; read it for custom parsers |
| xabbo/core (C#) | independent parsers, game state | good second opinion; also documents the old layouts |
| G-Earth `G-Earth-Api/.../parsers/` and G-Python `hparsers.py` | a few parsers (`HEntity`, `HEntityUpdate`) | documented layouts; G-Python reads strings as Latin-1 |
| Nitro (`billsonnn/nitro-renderer`) | parsers for the HTML5 client | same message names; layouts usually match AIR |
| **A live capture** (G-Earth logger, your own `bad-packets/*.hex`) | the truth for your build | always wins |

Two HabboPackets traps found while building this skill:
- **Enum layouts aren't in wire order.** `Users` is shown as `i[i(<variant> | ...)]` with
  the entity-type discriminator first, but on the wire the type int comes after the
  shared header (id, name, motto, figure, index, x, y, z, direction, **type**, tail).
- **Some layouts describe the parsed result, not the bytes.** `UserUpdate` shows a list
  of typed actions, but the wire carries a status **string** (`/sit 0.55 1/sign 7/`)
  that G-Rust parses.

So: use HabboPackets for names, field meaning and as a starting layout; confirm with a
capture before shipping a parser.

## 4. Verifying a layout: the 5-step method

1. `habbo_packets.py show <Name> --dir in|out` for the documented layout and field names.
2. Capture real bytes: G-Earth's logger, or let your extension save the first packet
   that doesn't parse (`logs/bad-packets/<Name>-<time>.hex`).
3. `habbo_packets.py decode --file that.hex --layout "<wire layout>"`. Exit 0 = every byte
   used. "N bytes left over" = the live client sends more than documented. "FAILED at
   byte N" = a field type is wrong before N.
4. Adjust the layout until every byte decodes with sane values; check with a second
   capture (different users, more entries).
5. Turn the capture into a test fixture, make the parser try the live layout first and
   the documented one second, and accept only a complete, plausible parse.

Real example (Users, one player, 2026-10 AIR): documented player layout leaves
`ff ff ff ff` over; adding one trailing int decodes every byte.

## 5. Chat packets

| Name | Dir | Layout | Notes |
|---|---|---|---|
| `Chat` | in | `i index, s text, i gesture, i style, i n, n x (s, s, B), i trackingId` | `index` = **room index**, not account id. Your own chat comes back as an echo with your index |
| `Shout` | in | same as `Chat` | |
| `Whisper` | in | same as `Chat` | whispers to you, and the echo of your own |
| `Chat` | out | `s text, i style, i tail` | copy `tail` from the user's own last chat when sending; default -1 |
| `Shout` | out | `s text, i style` | |
| `Whisper` | out | `s "target message", i style` | target and message share ONE string |
| `FloodControl` | in | `i seconds` | you're flood-muted: stop sending for that long |
| `RemainingMutePeriod` | in | `i seconds` | moderator mute |
| `StartTyping` / `CancelTyping` | out | empty | |

- **Bubble limit: 100 characters, counted in UTF-16 units** (an emoji counts as 2). Split
  longer text at word boundaries and pace bubbles (about 1 per 1.5 s is safe).
- Strip leading `/` and `:` from generated text: the client treats them as commands.

## 6. Room and user packets

| Name | Dir | Layout | Used for |
|---|---|---|---|
| `Users` | in | `i count`, then entries (section 7) | who's in the room: id, name, index, start tile |
| `UserUpdate` | in | `i count`, then entries (section 8) | positions, sitting, signs |
| `UserRemove` | in | `s index` (a number as a string) | someone left |
| `UserObject` | in | `i id, s name, s figure, s sex, s customData, s realName, B, i, i, i, B, s, B, B` | your own id and name |
| `InfoRetrieve` | out | empty | asks the server to resend `UserObject` |
| `RoomReady` | in | `s roomModel, i roomId` | you entered a room |
| `RoomEntryInfo` | in | `i roomId, B isOwner` | |
| `RoomEntryTile` | in | `i x, i y, i dir` | the door tile |
| `FloorHeightMap` | in | `B smallScale, i wallHeight, s rows` | which tiles are floor |
| `HeightMap` | in | width + per-tile shorts | floor + furni heights |
| `CloseConnection` | in | empty | you left the room |
| `GetGuestRoom` | out | `i roomId, i entering, i forward` | `(id, 0, 1)` = open the room like the navigator |
| `OpenFlatConnection` | out | `i roomId, s password, i ?` | the client sends it itself after `GetGuestRoom` |
| `GetHeightMap` | out | **gone** from AIR builds | G-Python's `RoomUsers.request()` still sends it: don't rely on it |

Incoming `Dance`, `Expression`, `Sleep` and similar carry the **room index**. G-Rust names
some of these fields `user_id`; they're still the index. Map index -> name from `Users`.

## 7. `Users` entry layout

Header (every entity):

```
i id, s name, s motto, s figure, i roomIndex, i x, i y, s z, i direction, i type
```

`type`: 1 player, 2 pet, 3 old-style (public room) bot, 4 user bot. Tail by type:

| Type | Tail |
|---|---|
| 1 player | `s sex, i groupId, i groupStatus, s groupName, s swimFigure, i achievementScore, B isModerator, i <extra = -1>` |
| 2 pet | `i subType, i ownerId, s ownerName, i rarity, B saddle, B riding, B canBreed, B canHarvest, B canRevive, B hasBreedingPermission, i level, s posture` |
| 3 old bot | (nothing) |
| 4 bot | `s sex, i ownerId, s ownerName, i n, n x u skills` |

`<extra>`: the live AIR client (2026-10) sends one more int after `isModerator`, not in any
public source. Parse defensively: try the live tail, then the documented one; if a tail
still doesn't fit, scan forward to the next plausible header (sane name/motto/figure
strings, direction 0-7, type 1-4) rather than losing everyone after the bad entry.

## 8. `UserUpdate` and its status string

Wire layout per entry (live AIR, 2026-10):

```
i index, i x, i y, s z, i headDir, i bodyDir, i <extra = 0>, s status
```

The `<extra>` int is missing from G-Earth, G-Rust and xabbo. With one entry, the
documented layout reads the extra int as an empty status (no error, status silently
lost); with two or more, the second entry is misaligned ("truncated string").

Status is `/`-separated `key value` pairs:

```
/flatctrl 4/sit 0.55 1/sign 7/mv 12,5,0.0/
```

| Key | Meaning |
|---|---|
| `flatctrl N` | room rights level |
| `mv x,y,z` | walking to tile x,y |
| `sit z canStand` | sitting at height z |
| `lay z` | lying |
| `sign N` | holding sign N (0-17), shows for a few seconds |
| `gst X` | gesture (smile, sad, ...) |
| `wf` | skip position update |

## 9. Avatar action packets and value tables

| Name | Dir | Layout | Values |
|---|---|---|---|
| `MoveAvatar` | out | `i x, i y` | target tile; the server pathfinds |
| `LookTo` | out | `i x, i y` | face that point |
| `Dance` | out | `i style` | 0 stop, 1 normal, 2 pogo-mogo, 3 duck funk, 4 the rollie (2-4 need HC) |
| `Dance` | in | `i index, i style` | |
| `ChangePosture` | out | `i posture` | 0 stand, 1 sit on the floor (fails while walking) |
| `AvatarExpression` | out | `i expression` | 1 wave, 2 blow kiss*, 3 laugh*, 5 idle (the client's own AFK report), 6 jump*, 7 thumbs up (*HC) |
| `Expression` | in | `i index, i expression` | |
| `Sign` | out | `i sign` | 0-10 numbers, 11 heart, 12 skull, 13 exclamation, 14 soccer ball, 15 smile, 16 red card, 17 yellow card |
| `Sleep` | in | `i index, B sleeping` | Zzz on/off |

HC-only actions silently do nothing on a non-HC account: make them opt-in.

`LookTo` targets far outside any room give a fixed facing wherever you stand:
`(-9999,-9999)` dir 0, `(500,0)` dir 2, `(9999,9999)` dir 3, `(5000,9999)` dir 4,
`(0,9999)` dir 5, `(-9999,9999)` dir 6, `(-9999,0)` dir 7 (found in-game).

## 10. Tiles, floor map, doors, directions

- A tile is (x, y) plus height z (a string). Use Chebyshev distance `max(|dx|,|dy|)` for
  "within N tiles".
- `FloorHeightMap.rows`: rows separated by `\r`; column = x, row = y; `x` = no floor,
  `0`-`9` then `a`-`z` = floor height level.
- `HeightMap` shorts (per G-Rust): `-1` = not a tile, else height = `(v & 16383) / 256`,
  bit `16384` = stacking blocked. Includes furni.
- The **door**: walking onto it leaves the room. Get it from `RoomEntryTile`; as a backup,
  treat floor tiles with at most one floor neighbour (4-way) as dead ends.
- Directions 0-7 clockwise from north: 0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW
  (same in `Users`, `UserUpdate`, G-Python `HDirection`). Screen appearance depends on
  the isometric camera; check in-game.

## 11. Other packets worth knowing

Look these up with `habbo_packets.py show` before use; confirm with a capture.

| Area | Names (search terms) |
|---|---|
| Profiles | `GetExtendedProfile` (out), `ExtendedProfile`, `RelationshipStatusInfo` |
| Friends / messenger | `FriendListUpdate` (custom parser), `NewConsole`, `SendMsg` |
| Furni in room | `Objects`, `ObjectAdd`, `ObjectUpdate`, `ObjectRemove`, `Items`, `ItemAdd` (custom) |
| Inventory | `FurniList`, `FurniListAddOrUpdate`, `FurniListRemove` |
| Trading | `TradingOpen`, `TradingItemList`, `TradingAccept`, `TradingConfirmation` |
| WIRED | search `Wired` (`WiredFurniTrigger`, `WiredFurniAction`, ...); for room variables prefer the official WIRED Web API |
| Navigator | `GetGuestRoom`, `GetGuestRoomResult` (long, optional tail) |
| Room moderation (as room owner) | `KickUser`, `MuteUser`, `BanUserWithDuration`, `RemoveRights`, `GetBannedUsersFromRoom` (out); `BannedUsersFromRoom` (in) |

`habbo_packets.py search <text> --templates` finds names and shared structures.
