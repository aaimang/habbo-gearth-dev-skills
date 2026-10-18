# Habbo WIRED Web API: full reference

Sources: the official Swagger UI (habbo.com/api/public/api-docs, "Habbo Web API 1.0.0",
OAS 3.0), the WIRED team's plain-language explainer, and the source of the official
wrappers (github.com/Habbo-API-Wrappers). The Swagger page itself is behind bot
protection (HTTP 463 for scripts; open it in a browser); the `/api/public/...`
endpoints are not. **Exact request/response shapes: `openapi-spec.md`** (taken from the
live spec). This file is about meaning and patterns.

Last checked: 2026-10-18.

## Contents
1. Access and auth
2. Terminology
3. Entity ids (the part everyone gets wrong)
4. Resource 1: a variable
5. Resource 2: a variables profile
6. Other WIRED endpoints (list, batch, pagination, count, bulk delete, user lookup)
7. Non-WIRED public endpoints
8. Schemas (names from Swagger)
9. Errors
10. 64-bit values
11. Level Up add-on subvariables
12. Patterns and recipes

## 1. Access and auth

- The room needs the furni **"Variable Global Add-on: Web API"**. 150 credits + 150
  diamonds (2+1 deal), not tradable, not in the BC warehouse.
- **The box in game** (seen by the user on 2026-10-18; window title "Wired Furni",
  "VARIABLE GLOBAL ADD-ON / Web API", link "Open API documentation"):
  - **API key for reading** and **API key for writing**, each with
    Generate (Regenerate once one exists), Clear and Copy.
  - **Extra permissions: "Allow mass deletion"**, off by default. It "enables
    access to the /variables/bulk-delete endpoint". Ticking it shows an "Are you
    sure?" dialog: bulk-delete irreversibly deletes all contents of variables; test
    on test variables in a different room first. Without it, expect bulk-delete to
    be refused (probably 403; unverified).
  - **Ready** saves, **Cancel** discards. Changes to keys and permissions only
    apply after Ready.
  - Usage warning in the box: keys are for "dedicated HTTPS endpoints"; nobody
    else can see the box contents; don't share the keys; **after changing variable
    configurations in the room, you may need to reload the room for the API to work
    properly** (so a new or renamed variable can 404 until the room reloads).
  - Keys look like ~43-character URL-safe random strings (`A-Z a-z 0-9 - _`).
    Regenerate = old key stops working; Clear = presumably no access of that kind.
  - Least privilege: a read-only app only needs the read key; leave the write key
    cleared until writes are needed, and keep mass deletion off unless the app
    really uses bulk-delete.
- Each room has a **read key** and a **write key**, sent as headers. Per the spec:
  - GET endpoints: `X-Wired-Read-Key` only.
  - PUT / PATCH / DELETE / bulk-delete: `X-Wired-Write-Key` only.
  - Batch: **both**.
  The wrappers simply send both on every call, which also works. Keys come from the
  room's wired settings (the Web API add-on box).
- Hosts (from `wired_api_python.param.hotel`):
  `www.habbo.com`, `.com.br`, `.de`, `.es`, `.fi`, `.fr`, `.it`, `.nl`, `.com.tr`, and
  the sandbox `sandbox.habbo.com` (hotel "S2"). Use the sandbox for experiments.
- `GET /api/public/ping` answers 200 without keys (good health check).
- Every WIRED endpoint can return **429 Rate limit exceeded** (also per operation
  inside a batch). The spec gives no numbers. Poll gently (seconds, not
  milliseconds), batch writes, honour `Retry-After` if present, back off on 429/5xx.
- Official explorer app (reads and edits variables in the browser):
  https://wired.habbo.com/variables-explorer

**Secrets:** treat both keys like passwords. `.env` (gitignored), never logged,
never in a browser bundle or a public repo. Anyone with the write key can rewrite
every variable in the room. If a key leaks, regenerate it in game.

## 2. Terminology

| Term | Values |
|---|---|
| scope | `user`, `furni`, `global` |
| target kind (scope `user`) | `users`, `pets`, `bots` |
| target kind (scope `furni`) | `furni`, `furni-bc`, `wall-items`, `wall-items-bc` |
| entity | anything that can hold permanent variables (a furni, a user, a pet, a bot) |
| entity id | number identifying the entity, in API form (see section 3) |

Only **permanent** variables are visible to the API.

## 3. Entity ids

- **Users, pets, bots:** API id = the same id WIRED's internal identifier variables
  use (for users: the numeric user id, not the per-room unit index).
- **Wall items:** in game the id is negative. `API_ID = IN_GAME_ID * -1`.
- **BC items:** in game they are offset. `API_ID = IN_GAME_ID - (0x7FFFFFFF - 0xFFFF)`
  (`0x7FFFFFFF - 0xFFFF = 2147418112`). Use target kind `furni-bc` / `wall-items-bc`.
- A BC wall item is both: negate first, then subtract the offset.
- Converter: `scripts/furni_ids.py` (`to_furni_id`, `from_furni_id`), port of the
  official `assets/furni-id-conversion.ts`.
- The public Habbo user API only exposes `uniqueId` (like `hhus-...`), never the
  numeric user id. To get a user's entity id, use the user lookup endpoint (section 6).

Unverified: whether ids seen in G-Earth packets for wall items and BC furni already
use the in-game form above. Check one item against the variables explorer before
relying on it.

## 4. Resource 1: a variable

Identified by the binding (variable name, entity). Representation:

```json
{ "value": "0", "creation_time": "2026-09-01T19:26:09.664Z", "update_time": "2026-09-01T19:26:09.664Z" }
```

`value` is a signed 64-bit integer **as a decimal string** (the explainer showed a bare
number; the spec says string).

It exists if the entity owns that variable in game.

| Method | Path | Meaning |
|---|---|---|
| GET | `/api/public/rooms/{roomId}/variables/{scope}/{variableName}/{targetKind}/{entityId}` | read |
| PUT | same | create, or replace if it exists (like WIRED Effect: Give Variable with "override existing variable") |
| PATCH | same | change `value` only (like Change Variable Value, "assign") |
| DELETE | same | remove it from the entity (like Remove Variable); 204, no body |
| GET | `/api/public/rooms/{roomId}/variables/global/{variableName}` | read a global |
| PATCH | same | change a global |

Body for PUT/PATCH: `{"value": "<int64 as string>"}`, e.g. `{"value": "7"}`. Globals
always exist: no PUT/DELETE.

## 5. Resource 2: a variables profile

Identified by the entity only. A profile is all variables of one entity.

| Profile | Exists when | Methods |
|---|---|---|
| furni | the furni is in the room (may be empty) | GET, PATCH (no PUT/DELETE: that would be placing/picking up) |
| global | always | GET, PATCH |
| user / pet / bot | it holds at least ONE permanent variable in this room | GET, PATCH, DELETE |

Paths:
- `GET|PATCH|DELETE /api/public/rooms/{roomId}/variables_profile/user/{targetKind}/{entityId}`
- `GET|PATCH /api/public/rooms/{roomId}/variables_profile/furni/{targetKind}/{entityId}`
- `GET|PATCH /api/public/rooms/{roomId}/variables_profile/global`

**DELETE on a user profile removes all their variables.** The API cannot create a user
profile, so the user must visit the room and get a variable again before the API can
see them. Recommended: give every visitor an `api_registered` variable on room entry;
to "reset" someone, PATCH every variable to `null` except `api_registered`.

**PATCH a profile = a batch for one entity:**

```json
{ "variables": { "variable_name1": "7", "variable_name2": null } }
```

`variable_name1` is created or updated; `null` deletes `variable_name2`. For the global
profile, values can't be `null` (globals can't be deleted).

## 6. Other WIRED endpoints

**List variable names in the room**
`GET /api/public/rooms/{roomId}/variables` -> three lists: `users`, `furni`, `global`.

**Batch (same variable, many entities)**
`POST /api/public/rooms/{roomId}/variables/{scope}/{variableName}/batch`, 1 to **50**
operations, needs **both** keys:

```json
{ "requests": [
  { "op_id": "a1", "method": "GET",    "path": "users/123" },
  { "op_id": "a2", "method": "PUT",    "path": "users/456", "body": { "value": "10" } },
  { "op_id": "a3", "method": "PATCH",  "path": "furni/789", "body": { "value": "3" } },
  { "op_id": "a4", "method": "DELETE", "path": "pets/42" }
] }
```

`path` is `{targetKind}/{entityId}` relative to the variable, no leading slash.
`op_id` is optional, any string you choose; it's echoed back. Response:

```json
{ "results": [ { "op_id": "a1", "status": 200, "body": { "value": "5", "creation_time": "...", "update_time": "..." } },
               { "op_id": "a4", "status": 204 },
               { "op_id": "a2", "status": 400, "error": { "code": "wired.variables.invalid_target", "message": "wired.variables.invalid_target" } } ] }
```

Each entry is 200 with `body`, 204 without, or 400/403/404/429/500 with `error`. A
batch call can return 200 while single operations failed: check every `status`.

**Paginated holders and counts**
- `GET /api/public/rooms/{roomId}/variables/{scope}/{variableName}/{targetKind}`
  query: `order_by` = `value` | `creation_time` | `update_time`, `order_dir` = `asc` |
  `desc`, `page` (from 1; `page=0` is a 400), `size` (default 50, values over 100 are
  silently clamped to 100). Response `{items, page, size}`; each item is
  `{variable: {value, creation_time, update_time}, user: {unique_id, name, id}}`
  (verified live; `pet` / `bot` / furni keys expected likewise). Stop paging when
  `items` is shorter than `size`.
- `GET .../{targetKind}/count` -> `{ "count": n }`.
- Polling recipe: keep a variable you update on purpose (e.g. `last_seen` or
  `api_registered`) and poll with `order_by=update_time&order_dir=desc` (or
  `creation_time` for newcomers), stopping at the first item you've already seen.

**Bulk delete (remove variables from ALL holders)**
`POST /api/public/rooms/{roomId}/variables/bulk-delete` body `{"variables": ["a", "b"]}`,
answers 204. Deletes the stored values from every user, pet, bot, furni and wall
item; the variable definitions stay configured. Destructive and room-wide: confirm
with the user before calling it.

**User lookup**
`GET /api/public/rooms/{roomId}/variables_profile/user/users?name=<name>` or
`?unique_id=<uniqueId>` -> that user's profile including `user: {unique_id, name, id}`.
Only works if the profile exists (they have a variable in the room), else 404
`wired.variables.entity_not_found`. Name matching is case-insensitive (verified). This
is the way to turn a name into the entity id. A variable given in game without a
value reads back as `"-1"`.

## 7. Non-WIRED public endpoints (no keys)

| Method | Path | What |
|---|---|---|
| GET | `/api/public/achievements` | all achievements |
| GET | `/api/public/achievements/{id}` | a user's achievements |
| GET | `/api/public/badge/owners/{badgeCode}` | badge owner details |
| GET | `/api/public/groups/{id}` and `/{id}/members` | group, members |
| POST | `/api/public/marketplace/stats/batch` | marketplace stats, batched |
| GET | `/api/public/ping` | health |
| GET | `/api/public/rooms/{roomId}` | room info |
| GET | `/api/public/lists/hotlooks` | hot looks (XML in the wrappers) |
| GET | `/api/public/users?name=` | user by name (gives `uniqueId`) |
| GET | `/api/public/users/{id}` + `/friends` `/groups` `/rooms` `/badges` `/profile` | by unique id |
| GET | `/api/public/matches/v1/...`, `/minigame/derby/v1/...`, `/skills/...`, `/users/by-playerId/{id}` | Habbo Origins |

## 8. Schemas (Swagger names)

`WiredError`, `WiredVariable`, `WiredRoomVariables`, `WiredPagedVariables`, `WiredCount`,
`WiredBatchResults`, `WiredVariableMap`, `WiredProfileBase`, `WiredUserProfileTarget`,
`WiredNamedProfileTarget`, `WiredIdProfileTarget`, `WiredUserProfile`, `WiredPetProfile`,
`WiredBotProfile`, `WiredFurniProfile`, `WiredFurniBcProfile`, `WiredWallItemProfile`,
`WiredWallItemBcProfile`, `WiredGlobalProfile`, `WiredAnyUserProfile`,
`WiredAnyFurniProfile`, `WiredVariablesProfile`, `WiredValueWrite`, `WiredVariablesPatch`,
`WiredGlobalVariablesPatch`, `WiredBatchOperationBody`, `WiredBatchOperationError`,
`WiredBatch{Get,Put,Patch,Delete}OperationRequest`, `WiredBatchOperationRequest`,
`WiredBatchOperationResult{WithBody,NoContent,Error}`, `WiredBatchOperationResult`,
`WiredBulkDelete`, `WiredBatchRequest`.

If exact field shapes matter, ask the user to expand the schema in the Swagger UI
and paste it; don't guess.

## 9. Errors

- Error bodies are `WiredError`: `{"error": "<code>"}`, e.g. `{"error": "not-found"}`
  (seen live). Batch op errors use `{code, message}` like `wired.variables.invalid_target`.
- Spec'd codes: 400 bad request, **403 forbidden (bad or missing key)**, 404 not found
  (room, variable value/definition, profile), 429 rate limit. Deletes answer 204.
- An unknown room or a room without the add-on answered 404 `not-found` with no keys.

## 10. 64-bit values (decimal strings)

Values are **signed 64-bit integers, sent and received as decimal strings** (`"7"`).
That avoids precision loss on the wire, but you still convert:
- Convert with `int(v)` / `BigInt(v)` on read and `str(n)` / `n.toString()` on write.
- **JavaScript/TypeScript:** if a wrapper or your code turns them into JSON numbers, `JSON.parse`/`JSON.stringify` corrupt numbers above 2^53.
  Use `bigint` with `json-with-bigint` (what the Node wrapper and the variables
  explorer do). Build for this even if your values are small.
- **Python:** ints are exact. Watch only for float conversions (`float(v)`, numpy,
  pandas) and clamp to `-2**63 .. 2**63-1` before writing.
- **PHP:** fine on 64-bit builds; `json_decode(..., flags: JSON_BIGINT_AS_STRING)` on 32-bit.
- **Rust:** `i64`; **C#:** `long`.

## 11. Level Up add-on subvariables

A level-up variable stores raw XP; level, progress etc. are derived. Use
`scripts/level_upper.py` (Python port of the official snippet, verified identical to
the TS on 4,921 cases) or `assets/level-upper.ts`.
- `LevelUpper.linear(step_size, max_level)`
- `LevelUpper.interpolate({level: xp, ...})`
- `LevelUpper.exponential(initial_xp, strength_percent, max_level)`
- Methods: `current_level`, `total_xp_required`, `progress`, `progress_percentage`,
  `xp_remaining`, `is_maxed`, `max_level`, `max_xp`, `bounded_value`.
- **Known bug:** linear `max_xp` must be `(max_level - 1) * step_size`. The original
  snippet and the wrappers (Python 0.1.4 at least) still return `max_level * step_size`.
  Our port and `assets/level-upper.ts` have the fix.

## 12. Patterns and recipes

- **Leaderboard:** list holders of `points` with `order_by=value&order_dir=desc&size=10`.
- **Give a reward to many users:** one batch (<= 50 ops) per variable, then check
  each result's `status`.
- **Mirror a profile into your app:** user lookup by name -> keep `user.id` -> GET or
  PATCH the profile by id afterwards.
- **Website / Discord bot:** do API calls on a server you control (keys stay
  server side). A browser page must never hold the write key.
- **Combining with G-Earth:** a G-Earth extension can read live room events (packets)
  and the Web API can persist state in WIRED variables. The Web API is the official,
  ToS-friendly part; G-Earth is not (see the `habbo-gearth` skill).
