# Habbo Web API: the official OpenAPI spec, as Markdown

Extracted from the live Swagger UI at https://www.habbo.com/api/public/api-docs/
(opened in a real browser on 2026-10-18 and read from the loaded spec object; scripts
get HTTP 463 on that page). Spec: OpenAPI 3.0.0, "Habbo Web API" version 1.0.0,
description "Habbo Web API documented with Swagger." No `servers` and no security
schemes are declared: the keys are plain required header parameters.

This file is the **source of truth for shapes**. `wired-web-api.md` explains meaning
and patterns; when the two disagree, this file wins (and fix the other one).

## Contents
1. What the spec says that's easy to miss
2. WIRED Variables endpoints (tag "Wired Variables")
3. WIRED schemas
4. Other public endpoints
5. Origins endpoints

## 1. Easy to miss

- **Values are decimal STRINGS**, both ways: `WiredVariable.value`,
  `WiredValueWrite.value`, batch `body.value` and profile patch values are all
  `"7"`, not `7` ("Signed 64-bit integer encoded as a decimal string to preserve
  precision"). Parse with `int(v)` / `BigInt(v)`; send `str(n)`. The official
  wrappers send JSON numbers; that may be accepted, but the spec says strings.
- **Which key goes where:** GET endpoints require only `X-Wired-Read-Key`; PUT, PATCH,
  DELETE and bulk-delete require only `X-Wired-Write-Key`; **batch requires both**.
- **Status codes:** 200 with a body, **204 with no body** for DELETE (variable,
  profile) and bulk-delete; **403 Forbidden** for key problems; 404 room/variable/
  profile not found; **429 rate limit exceeded**; 400 bad request. Every error body is
  `WiredError` `{"error": "<code>"}`.
- **Batch:** 1 to 50 operations; `op_id` is optional; per-op results are `200` with
  `body`, `204` without body, or `400/403/404/429/500` with
  `error {code, message}` (message currently mirrors code, e.g.
  `wired.variables.invalid_target`). A batch can be rate limited per operation (429
  inside a 200 response).
- **Profiles name the target by key:** `user` (`{id, name, unique_id}`), `pet` and
  `bot` (`{id, name}`), `furni`, `furni_bc`, `wall_item`, `wall_item_bc` (`{id}`).
  Live: values given as JSON numbers are accepted too, but responses are always strings.
  Global profile has no target key. Ids here are int64 numbers, `entityId` in paths
  is a string.
- **Bulk delete needs the box's "Allow mass deletion" permission** (in game, off by
  default; not mentioned in the spec).
- **Bulk delete keeps the definitions:** it deletes stored values from users, pets,
  bots, furni and wall items; the variables stay configured in the room.
- **Paged list items are untyped** in the spec (`array<object>`). Observed shape (from
  the wrappers): each item has `variable` (`WiredVariable`) plus the holder under
  `user` / `pet` / `bot` / furni key. Verify against a live response before relying on it.
- `GET /users` and `GET /users/{id}` support `If-None-Match` and return **304** when
  unchanged (ETag caching). The WIRED endpoints don't declare this.
- No rate limit numbers are in the spec, only the 429 response.

## 1b. Verified live (2026-10-18, www.habbo.com, a real room, read key only)

| Request | Result |
|---|---|
| `GET /variables` with only `X-Wired-Read-Key` | 200 `{"users":["troll"],"furni":[],"global":[]}`: **reads work with the read key alone** |
| `GET /variables_profile/global` (no globals) | 200 `{"variables":{}}` |
| list holders, nobody holds it | 200 `{"items":[],"page":1,"size":3}` (`size` echoes the request) |
| count, nobody holds it | 200 `{"count":0}` |
| no key header | **403 `{"error":"wired.variables.key_invalid"}`** |
| wrong key | 403 `{"error":"wired.variables.key_invalid"}` (same as missing) |
| global or variable name that doesn't exist | 404 `{"error":"wired.variables.not_found"}` |
| list holders of a variable that doesn't exist | 404 `wired.variables.not_found` |
| profile lookup by name, user has no variables in the room (even the owner) | 404 `{"error":"wired.variables.entity_not_found"}` |
| invalid target kind (`.../user/x/badkind`) | 400 `{"error":"wired.variables.invalid_target"}` |
| non-numeric entity id (`.../user/users/abc`) | 404 `{"error":"not-found"}` (generic router 404, not a `wired.*` code) |
| `If-None-Match: <etag>` on `GET /variables` | **304, empty body**: WIRED GETs send weak ETags and support revalidation (not in the spec) |

With one holder (a user given the variable in game, no value set):

```json
// GET /variables/user/troll/users?size=3&order_by=update_time&order_dir=desc
{"items":[{"variable":{"value":"-1","creation_time":"2026-10-18T08:25:36.629Z","update_time":"2026-10-18T08:25:36.629Z"},
           "user":{"unique_id":"hhus-<32 hex>","name":"<name>","id":<int64>}}],
 "page":1,"size":3}
// GET /variables_profile/user/users?name=<name>   (same for ?unique_id= and /users/{id})
{"user":{"id":<int64>,"name":"<name>","unique_id":"hhus-<32 hex>"},
 "variables":{"troll":{"value":"-1","creation_time":"...","update_time":"..."}}}
```

| Request | Result |
|---|---|
| paged item shape | `{variable: WiredVariable, user: {unique_id, name, id}}` (holder key is `user` for users; `pet`/`bot`/furni keys expected likewise) |
| variable given in game **without a value** | `"value": "-1"` (matches the wrappers' default of -1 for PUT) |
| `GET /variables/user/troll/users/{id}` | 200 `WiredVariable` |
| profile by `name`, `unique_id`, or `/users/{id}` | all 200, identical body |
| name lookup with different case (`SOMENAME` for `somename`) | 200: **name lookup is case-insensitive** |
| right id, wrong target kind (`pets/{userId}`) | 404 `wired.variables.not_found` |
| `size=101` | 200 with `"size":100`: **silently clamped to 100** (read `size` back) |
| `page=0` | 400 `wired.variables.invalid_target` (pages start at 1; odd error code) |
| user `id` in API | the numeric account id, same one the public user API hides |

Headers seen: `Content-Type: application/json; charset=utf-8`, a weak `etag`, and
`X-DIS-Request-ID` (include it when reporting problems). **No rate limit or
Retry-After headers** on normal responses; 429 not triggered yet.

Error codes seen so far: `wired.variables.key_invalid`, `wired.variables.key_missing`
(batch without the read key), `wired.variables.not_found`,
`wired.variables.entity_not_found`, `wired.variables.invalid_target`, plus the
generic `not-found`. Branch on these codes, not just the status.

### Writes (verified live 2026-10-18, on the tester's own value, restored afterwards)

| Request | Result |
|---|---|
| PATCH with **only the read key** | 403 `wired.variables.key_invalid` (read key can't write) |
| PATCH `{"value": "5"}` (string) | 200, returns `"value":"5"` |
| PATCH `{"value": 6}` (JSON number) | **200, also accepted**; returned as `"6"`. Responses are always strings |
| PATCH with the same value it already has | 200 and **`update_time` still changes** (no-op writes are not free: they reorder `order_by=update_time` lists) |
| batch with only the write key | 403 **`wired.variables.key_missing`** (batch needs both keys) |
| batch with both keys | 200 `{"results":[{"status":200,"body":{...},"error":null,"op_id":"get-me"}, ...]}`: successful ops carry **`"error": null`**, not an absent key; ops run in order (GET saw the old value, PATCH the new) |
| profile PATCH `{"variables":{"troll":"-1"}}` | 200, full profile back (`user` + `variables`) |

So: send strings (spec) but numbers work; always parse responses as strings; check
`status`, not the presence of `error`, in batch results.

### Errors (verified live 2026-10-31)

| Request | Result |
|---|---|
| Any GET on a room with the add-on but no saved keys | 403 `wired.variables.key_missing`, even with a key sent |
| Any request on a room without the add-on | 404 `not-found`, but a bad target kind still gives 400 `invalid_target` |
| Unknown scope, or batch on a global variable | 404 with an empty body |
| Non-numeric entity id | 404 `not-found`, before any key check |
| `order_by` that is not a known field | 400 `invalid_target` |
| PATCH value that is text, a decimal, a boolean or above int64 | 400 `request-failed-non-200`, before a missing variable is reported |
| PATCH value null, or no body | 400 `wired.variables.invalid_value` |
| Bulk delete with an empty list | 400 `wired.variables.bulk_delete_empty`, even with "Allow mass deletion" off |
| Batch with an empty list | 400 `wired.variables.batch_empty`, before any key check |
| Error answers | Carry an ETag, on writes too |
| Default Python client User-Agent on habbo.com | HTTP 463, so send your own User-Agent |

Still unverified: bulk-delete without "Allow mass deletion", PUT/DELETE behaviour,
pets/bots/furni holder keys, rate limit numbers.

## 2. WIRED Variables endpoints

Common path parameters: `roomId` integer; `scope` enum `user | furni` (global has its
own paths); `variableName` string; `entityId` string; `targetKind` enum
`users | pets | bots` when scope is `user`, `furni | furni-bc | wall-items | wall-items-bc`
when scope is `furni`.

| Method | Path (prefix `/api/public/rooms/{roomId}`) | Key header | Body | Success | Errors |
|---|---|---|---|---|---|
| GET | `/variables` | Read | | 200 `WiredRoomVariables` | 403 404 429 |
| GET | `/variables/{scope}/{variableName}/{targetKind}/{entityId}` | Read | | 200 `WiredVariable` | 400 403 404 429 |
| PUT | same | Write | `WiredValueWrite` | 200 `WiredVariable` | 400 403 404 429 |
| PATCH | same | Write | `WiredValueWrite` | 200 `WiredVariable` | 400 403 404 429 |
| DELETE | same | Write | | **204** | 400 403 404 429 |
| GET | `/variables/{scope}/{variableName}/{targetKind}` | Read | query `order_by` (`value`, `creation_time`, `update_time`), `order_dir` (`asc`, `desc`), `page`, `size` (integers) | 200 `WiredPagedVariables` | 400 403 404 429 |
| GET | `/variables/{scope}/{variableName}/{targetKind}/count` | Read | | 200 `WiredCount` | 400 403 404 429 |
| POST | `/variables/bulk-delete` | Write | `WiredBulkDelete` | **204** | 400 403 404 429 |
| POST | `/variables/{scope}/{variableName}/batch` | **Read + Write** | `WiredBatchRequest` | 200 `WiredBatchResults` | 400 403 404 429 |
| GET | `/variables/global/{variableName}` | Read | | 200 `WiredVariable` | 403 404 429 |
| PATCH | `/variables/global/{variableName}` | Write | `WiredValueWrite` | 200 `WiredVariable` | 400 403 404 429 |
| GET | `/variables_profile/user/users` | Read | query `name` or `unique_id` | 200 `WiredUserProfile` | 400 403 404 429 |
| GET | `/variables_profile/user/{targetKind}/{entityId}` (users, pets, bots) | Read | | 200 `WiredAnyUserProfile` | 400 403 404 429 |
| PATCH | same | Write | `WiredVariablesPatch` | 200 `WiredAnyUserProfile` | 400 403 404 429 |
| DELETE | same | Write | | **204** | 400 403 404 429 |
| GET | `/variables_profile/furni/{targetKind}/{entityId}` (furni, furni-bc, wall-items, wall-items-bc) | Read | | 200 `WiredAnyFurniProfile` | 400 403 404 429 |
| PATCH | same | Write | `WiredVariablesPatch` | 200 `WiredAnyFurniProfile` | 400 403 404 429 |
| GET | `/variables_profile/global` | Read | | 200 `WiredGlobalProfile` | 403 404 429 |
| PATCH | same | Write | `WiredGlobalVariablesPatch` | 200 `WiredGlobalProfile` | 400 403 404 429 |

404 descriptions in the spec, useful for error messages: "Room not found", "Room or
variable value not found", "Room or variable definition not found" (list, count,
batch), "Room or entity profile not found", "Room, entity profile, or stored variable
value not found" (profile PATCH/DELETE), "Room or stored global variable value not
found".

## 3. WIRED schemas

```text
WiredError            { error: string }                                   required: error
WiredVariable         { value: string(int64 as decimal), creation_time: date-time, update_time: date-time }
WiredRoomVariables    { users: string[], furni: string[], global: string[] }
WiredPagedVariables   { items: object[], page: integer, size: integer }
WiredCount            { count: integer }
WiredValueWrite       { value: string(int64 as decimal) }                 required: value
WiredBulkDelete       { variables: string[] }                             required: variables
WiredVariableMap      map<string, WiredVariable>
WiredProfileBase      { variables: WiredVariableMap }                     required: variables

WiredUserProfileTarget  { id: int64, name?: string, unique_id?: string }  required: id
WiredNamedProfileTarget { id: int64, name?: string }                      required: id
WiredIdProfileTarget    { id: int64 }                                     required: id

WiredUserProfile       = WiredProfileBase & { user: WiredUserProfileTarget }
WiredPetProfile        = WiredProfileBase & { pet: WiredNamedProfileTarget }
WiredBotProfile        = WiredProfileBase & { bot: WiredNamedProfileTarget }
WiredFurniProfile      = WiredProfileBase & { furni: WiredIdProfileTarget }
WiredFurniBcProfile    = WiredProfileBase & { furni_bc: WiredIdProfileTarget }
WiredWallItemProfile   = WiredProfileBase & { wall_item: WiredIdProfileTarget }
WiredWallItemBcProfile = WiredProfileBase & { wall_item_bc: WiredIdProfileTarget }
WiredGlobalProfile     = WiredProfileBase
WiredAnyUserProfile    = WiredUserProfile | WiredPetProfile | WiredBotProfile
WiredAnyFurniProfile   = WiredFurniProfile | WiredFurniBcProfile | WiredWallItemProfile | WiredWallItemBcProfile
WiredVariablesProfile  = any of the eight profiles above

WiredVariablesPatch        { variables: map<string, string | null> }   required (null deletes)
WiredGlobalVariablesPatch  { variables: map<string, string> }          required (no null)

WiredBatchRequest   { requests: WiredBatchOperationRequest[] }  1..50 operations, against the variable in the route
WiredBatchOperationRequest =
    { op_id?: string, method: "GET",    path: "<targetKind>/<entityId>" }
  | { op_id?: string, method: "PUT",    path, body: { value: string } }
  | { op_id?: string, method: "PATCH",  path, body: { value: string } }
  | { op_id?: string, method: "DELETE", path }
  (path has no leading slash, e.g. "users/44")
WiredBatchResults   { results: WiredBatchOperationResult[] }     required: results
WiredBatchOperationResult =
    { op_id: string|null, status: 200, body: WiredVariable }
  | { op_id: string|null, status: 204 }
  | { op_id: string|null, status: 400|403|404|429|500, error: { code: string, message: string } }
```

Examples straight from the spec:

```json
// WiredBatchRequest
{"requests":[{"op_id":"get-user","method":"GET","path":"users/44"},
             {"op_id":"patch-user","method":"PATCH","path":"users/44","body":{"value":"7"}},
             {"op_id":"delete-user","method":"DELETE","path":"pets/12"}]}
// WiredBatchResults
{"results":[{"op_id":"get-user","status":200,"body":{"value":"7","creation_time":"2023-11-16T22:13:20Z","update_time":"2023-11-16T22:13:20Z"}},
            {"op_id":"delete-user","status":204},
            {"op_id":"invalid-target","status":400,"error":{"code":"wired.variables.invalid_target","message":"wired.variables.invalid_target"}}]}
// WiredVariableMap (inside every profile as "variables")
{"variable_name1":{"value":"7","creation_time":"2023-11-16T22:13:20Z","update_time":"2023-11-16T22:13:20Z"},
 "variable_name2":{"value":"11","creation_time":"2023-11-17T08:00:00Z","update_time":"2023-11-17T09:30:00Z"}}
// WiredVariablesPatch
{"variables":{"variable_name1":"7","variable_name2":null}}
// WiredGlobalVariablesPatch
{"variables":{"variable_name1":"7","variable_name2":"11"}}
```

## 4. Other public endpoints (no keys)

| Method | Path (prefix `/api/public`) | Params | 200 | Other |
|---|---|---|---|---|
| GET | `/achievements` | | array of achievements with level requirements | 404 |
| GET | `/achievements/{id}` | `id` = user unique id | the user's achievements | 404 |
| GET | `/badge/owners/{badgeCode}` | | owner count + localized name/description | 404 |
| GET | `/groups/{id}` | group id | group | 404 |
| GET | `/groups/{id}/members` | | members | 404 |
| POST | `/marketplace/stats/batch` | body `{roomItems: [{item: "<name>"}], wallItems: [{item: "<name>"}]}` | stats per item | 404 |
| GET | `/ping` | | OK | 503 when the backend is down |
| GET | `/rooms/{roomId}` | integer id | `{id, name, description, creationTime, habboGroupId, tags[], maximumVisitors, showOwnerName, ownerName, ownerUniqueId, categories[], thumbnailUrl, ...}` | 404 |
| GET | `/lists/hotlooks` | | **XML** list of hot looks | |
| GET | `/users?name=` | header `If-None-Match` optional | user | 304, 404 |
| GET | `/users/{id}` | unique id; `If-None-Match` | user | 304, 404 |
| GET | `/users/{id}/friends`, `/groups`, `/rooms`, `/badges`, `/profile` | unique id | lists / full profile, only if the profile is visible | 404 |

Less data is returned for users with limited profile visibility.

## 5. Origins endpoints (tag "origins", Habbo Origins)

| Method | Path (prefix `/api/public`) | Params |
|---|---|---|
| GET | `/matches/v1/{uniquePlayerId}/ids` | `offset`, `limit`, `start_time`, `end_time` -> string[] of match ids |
| GET | `/matches/v1/{uniqueMatchId}` | match details |
| GET | `/minigame/derby/v1/{uniquePlayerId}/ids` | `offset`, `limit`, `start_time`, `end_time`, `api_key` |
| GET | `/minigame/derby/v1/{uniqueDerbyId}` | `api_key` |
| GET | `/minigame/derby/v1/status` | `api_key`; current fishing derby status |
| GET | `/skills/{uniquePlayerId}` | `skillType` (required, enum `FISHING`) |
| GET | `/skills/leaderboard` | `skillType` (required, `FISHING`), `page` (min 1, default 1) |
| GET | `/users/by-playerId/{uniquePlayerId}` | -> uniqueHabbo id for an Origins player |

## Refreshing this file

Open the Swagger page in the built-in browser and run in the page:
`JSON.stringify(window.ui.specSelectors.specJson().toJS())`. That is the whole spec
(about 79 KB, 35 paths, 38 schemas on 2026-10-18). Diff it against this file.
