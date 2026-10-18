---
name: habbo-wired-api
description: Build Habbo tools with the official WIRED Web API, covering room variables over REST, X-Wired-Read-Key/X-Wired-Write-Key, variable profiles, batch, bulk delete, the Level Up add-on maths, furni id conversion, 64-bit values as strings, rate limits. Use whenever a task mentions WIRED variables, the Variable Global Add-on Web API, habbo.com /api/public, room variable keys, wired-api-python / wired-api-wrapper-node / habbo-api-wrapper-php or other Habbo Web API wrappers, or a website / Discord bot that reads or writes Habbo room state, even if the user only says "the Habbo API". Not for G-Earth extensions, packets or G-Python (use habbo-gearth for those).
---

# Habbo WIRED Web API

Two ways to make Habbo do things from code. Pick the right one first.

| Need | Use | Why |
|---|---|---|
| Read/write a room's **permanent WIRED variables** (scores, levels, inventories, flags) from a website, Discord bot, script or server | **WIRED Web API** (official REST) | Sanctioned by Habbo, no client needed, works while you're offline |
| React to **live in-room events** (chat, movement, entering users) or act as an avatar | **G-Earth extension**: use the **`habbo-gearth`** skill | Only way to see live packets. **Breaks Habbo ToS §5/§8**: say so |
| Both (e.g. live chat command that awards persistent points) | Extension for events (`habbo-gearth`), Web API for state (this skill) | Keeps state official and survives restarts |

Prefer the Web API whenever it can do the job.

## Reference map (read only what the task needs)

| File | Read when |
|---|---|
| `references/openapi-spec.md` | Exact request/response shapes, status codes, which key each endpoint needs (from the live Swagger spec; wins any disagreement) |
| `references/wired-web-api.md` | Any Web API work: meaning of resources, profiles rules, batch, pagination, ids, recipes |
| `references/wrappers.md` | Using or writing a wrapper (Python/Node/PHP APIs, versions, bugs found in their source) |
| `references/repos.md` | You need a link, a file to read in a repo, or a package version |
| `scripts/furni_ids.py` | Converting furni ids game <-> API (`python furni_ids.py` self-tests) |
| `scripts/level_upper.py` | Level Up add-on maths (fixed `max_xp`; verified equal to the TS on 4,921 cases) |
| `scripts/wired_smoke.py` | First contact with a room: read-only ping + list variables + global profile |
| `assets/*.ts` | The official TypeScript snippets (level-upper has the fix applied) |

## Web API in one screen

- Base: `https://www.habbo.com` (or `.com.br .de .es .fi .fr .it .nl .com.tr`; sandbox
  `https://sandbox.habbo.com`). Prefix `/api/public`.
- Room must have the **Variable Global Add-on: Web API** box. Headers:
  `X-Wired-Read-Key` for GETs, `X-Wired-Write-Key` for writes, **both for batch**.
  Keys are secrets. Missing/bad key = 403 `wired.variables.key_invalid`; unknown
  variable = 404 `wired.variables.not_found`; no profile = 404
  `wired.variables.entity_not_found`; rate limited = 429; deletes = 204. GETs send
  ETags (304 on `If-None-Match`). Verified live: `references/openapi-spec.md` 1b.
- In the box: Generate/Regenerate/Clear/Copy per key, **Ready** to save, and an
  **"Allow mass deletion"** tick (off by default) that gates `/variables/bulk-delete`.
  After changing variable configuration, reload the room or the API may not see it.
- **Values are int64 as decimal strings** (`{"value": "7"}`). Responses are always
  strings; numbers in request bodies are accepted too (verified). Read key can't
  write (403 `key_invalid`); batch without both keys = 403 `key_missing`. A PATCH to
  the same value still bumps `update_time`.
- Scopes `user` | `furni` | `global`. Target kinds: `users pets bots` /
  `furni furni-bc wall-items wall-items-bc`. Only **permanent** variables are visible.

| Method(s) | Path under `/api/public/rooms/{roomId}` |
|---|---|
| GET | `/variables` (all names: users, furni, global) |
| GET PUT PATCH DELETE | `/variables/{scope}/{name}/{targetKind}/{entityId}` |
| GET PATCH | `/variables/global/{name}` |
| GET | `/variables/{scope}/{name}/{targetKind}?order_by=value\|creation_time\|update_time&order_dir=asc\|desc&page=1&size=50` (max 100) |
| GET | `/variables/{scope}/{name}/{targetKind}/count` |
| POST | `/variables/{scope}/{name}/batch` `{"requests":[{"op_id","method","path":"users/123","body":{"value":"1"}}]}` 1-50 ops |
| POST | `/variables/bulk-delete` `{"variables":["a","b"]}` (ALL holders, destructive) |
| GET | `/variables_profile/user/users?name=` or `?unique_id=` (name -> entity id) |
| GET PATCH DELETE | `/variables_profile/user/{users\|pets\|bots}/{id}` |
| GET PATCH | `/variables_profile/furni/{kind}/{id}`, `/variables_profile/global` |

Semantics that matter:
- PUT = create or replace (Give Variable + override). PATCH = change `value` only.
  Globals always exist (no PUT/DELETE).
- Profile PATCH `{"variables": {"a": "7", "b": null}}` creates/updates `a`, deletes `b`.
- A user profile exists only while they hold >= 1 variable in the room, and the API
  can't create one. DELETE wipes all their variables. Give everyone an
  `api_registered` variable on entry and reset by PATCHing others to `null`.
- Furni profiles exist while the furni is in the room (no PUT/DELETE).
- Batch returns per-op `status`: a 200 batch can contain failures.

## Golden rules

1. **Ids:** wall items are negative in game (`api = -game`); BC items are offset
   (`api = game - 2147418112`) with the `-bc` kind. Use `scripts/furni_ids.py`.
   Users have no numeric id in the public user API: use the profile lookup by name.
2. **64-bit signed values as decimal strings.** Convert with `int()` / `BigInt()`, send
   `str(n)`. In JS never let them become `Number` (use `bigint`, and
   `json-with-bigint` if anything is a JSON number). Clamp to int64 before writing.
3. **Level Up linear `max_xp = (max_level - 1) * step_size`.** The official snippet and
   the Python wrapper (0.1.4) have the old formula. Use `scripts/level_upper.py`.
4. **Secrets:** keys in a gitignored `.env`, never logged, never in client-side code,
   never in URLs. Write key only on a server you control.
5. **Destructive calls need a yes from the user first:** profile DELETE, bulk-delete,
   batch DELETEs, PUT over existing values. Test on the sandbox or a test room.
   Recommend leaving "Allow mass deletion" off unless bulk-delete is really needed,
   and a cleared write key for read-only apps.
6. **Be gentle:** every endpoint can answer 429 (also per op inside a batch); no
   numbers published. Set timeouts (the Python wrapper sets none), back off on
   429/5xx, batch writes, poll every few seconds at most.
7. **Don't guess schemas.** Check `references/openapi-spec.md`. If something's missing
   or may have changed, open the Swagger page in the built-in browser (scripts get
   HTTP 463) and read `window.ui.specSelectors.specJson().toJS()`, or call the
   endpoint read-only and look.

## Combining with a G-Earth extension

All extension knowledge (protocol, packets, G-Python, store, templates, scripts) lives in
the **`habbo-gearth`** skill (`~/.claude/skills/habbo-gearth/`). From the Web API side,
only this matters: the extension calls the Web API from a **worker thread**, never from
a packet callback (G-Earth holds the packet while a callback runs), with timeouts and
429 back-off, and keys stay out of the extension's logs and any published zip.

## Starting a new project

1. Decide Web API vs extension vs both (table above). If an extension is involved,
   load `habbo-gearth` too and write down its ToS note.
2. Ask for: hotel, room id, which variables exist (or run `wired_smoke.py` with the
   user's keys in env), and whether writes are allowed yet. Keys go in a gitignored
   `.env`, never in chat; if a key was shown in a screenshot or chat, have the user
   Regenerate it (and press Ready).
3. Python: `uv add wired-api-python` (sync, `requests`) or a thin `httpx` client
   against the paths above; copy `scripts/furni_ids.py` and `scripts/level_upper.py`
   in as modules. Node: `wired-api-wrapper-node` with bigint end to end.
4. Build read paths first; add writes behind an explicit flag or confirmation.
5. Test without the network: fake the HTTP layer (inject the transport or monkeypatch
   `urlopen`), cover batch partial failures, 404 profiles, and int64 edges
   (`2**63 - 1`, `-2**63`, values above 2^53).

## Public text conventions

- Plain wording; keep the disclaimer "Unofficial fan project, not affiliated with or
  endorsed by Sulake Oy." in READMEs.
- Never commit secrets or `.env`; ask before committing or pushing on someone's behalf.
