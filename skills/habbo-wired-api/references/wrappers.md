# Official API wrappers

All three live under https://github.com/Habbo-API-Wrappers (MIT). The PHP one is the
original (by WiredSpast); Python and Node are ports. Checked 2026-10-18.

| Language | Repo | Package | Version | Deps |
|---|---|---|---|---|
| Python | Habbo-API-Wrapper-Python | `wired-api-python` (PyPI), import `wired_api_python` | 0.1.4, Python >= 3.9 | `requests` |
| Node/TS | Habbo-API-Wrapper-Node | `wired-api-wrapper-node` (npm) | 1.0.6 | `json-with-bigint` |
| PHP | Habbo-API-Wrapper-PHP | `wiredspast/habbo-api-wrapper-php` (Packagist) | v1.0.2, PHP >= 8.1 | PSR-18 client, ext-xml |

## Python (`wired-api-python`)

```python
from wired_api_python import HabboPublicAPI, Hotel, HabboApiException, UserTargetKind, FurniTargetKind, OrderBy, OrderDir

api = HabboPublicAPI.from_hotel(Hotel.COM)          # Hotel.S2 = sandbox
var = api.variables(room_id, read_key, write_key)   # sets X-Wired-Read-Key / X-Wired-Write-Key

var.list_all()                                       # VariablesListResult(users, furni, global_)
var.bulk_delete("a", "b")                            # returns bool, SWALLOWS errors

u = var.user()
u.get_variable("points", UserTargetKind.USERS, 123)
u.give_variable("points", UserTargetKind.USERS, 123, 10)     # PUT (default value=-1!)
u.change_variable("points", UserTargetKind.USERS, 123, 11)   # PATCH
u.remove_variable("points", UserTargetKind.USERS, 123)       # DELETE
u.list_holders("points", UserTargetKind.USERS, OrderBy.VALUE, OrderDir.DESCENDING, page=1, page_size=100)
u.count_holders("points", UserTargetKind.USERS)
u.get_profile_by_username("Name"); u.get_profile_by_unique_id("hhus-...")
u.get_profile(UserTargetKind.USERS, 123); u.remove_profile(...); u.change_profile(kind, id, {"a": 1, "b": None})
(u.build_batch_request("points")
   .give_variable("op1", UserTargetKind.USERS, 1, 5)
   .change_variable("op2", UserTargetKind.USERS, 2, 6)
   .execute_request())                               # BatchResult(results=[BatchResultEntry(op_id, status, body, error)])
u.build_change_profile_request(kind, id).change_or_give_variable("a", 1).remove_variable("b").execute_request()

f = var.furni()      # same shape; target kinds FURNI, FURNI_BC, WALL_ITEMS, WALL_ITEMS_BC
g = var.global_()    # get_variable, change_variable, get_profile, change_profile, build_change_profile_request
```

Gotchas found reading the source (0.1.4):
- **Sends values as JSON numbers and reads `value` as-is.** The server accepts number
  bodies (verified live), but responses are decimal strings (`"7"`), so
  `VariableResult.value` is a `str`: convert with `int()`. Batch results have
  `"error": null` on success, which its `"error" in data` check handles (`None`).
- **No HTTP timeout.** `requests` calls are made without `timeout=`, so a stalled
  connection hangs forever. Pass your own `requests.Session` with a timeout adapter,
  or wrap calls in a worker with a deadline. This matters in G-Earth callbacks
  (never call the API on the packet thread anyway).
- **Linear level-up `max_xp` bug** (`max_level * step_size`). Use `scripts/level_upper.py`.
- `bulk_delete` returns `False` on any error instead of raising.
- `give_variable` defaults `value=-1` if you omit it.
- The furni batch builder runs `sanitise_furni_id` (negate wall ids, strip the BC
  offset) but YOU still choose the right target kind. Use `scripts/furni_ids.py` to get
  both kind and id.
- `__version__` says 0.1.1 while the package is 0.1.4; check `pip show` for the truth.
- The transporter skips the body when it's falsy (`if body:`); never send `{}` and
  expect it to arrive.
- Synchronous only. For asyncio, run calls in a thread (`asyncio.to_thread`) or write a
  thin `httpx.AsyncClient` client against the paths in wired-web-api.md.

## Node (`wired-api-wrapper-node`)

- TypeScript sources in `src/` (`client.ts`, `resources/variables/*`, `addon/levelUp/*`,
  `util/furniIdSanitiser.ts`, `examples/basicUsage.mts`).
- Uses `json-with-bigint` so variable values are `bigint`. Keep them as `bigint` end to
  end; `Number(v)` reintroduces the 2^53 problem.
- Same resource layout as Python (user / furni / global, batch and profile builders,
  `OrderBy`, `OrderDir`, `UserTargetKind`, `FurniTargetKind`, `Hotel`).

## PHP (`wiredspast/habbo-api-wrapper-php`)

- `HabboPublicAPI`, PSR-18 transport (`php-http/discovery` picks your client).
- Same structure; the Python package docstring says it's "a Python port of" this repo,
  so the PHP code is the reference when the ports disagree.

## Writing your own wrapper

Announce it to the WIRED team so it gets listed. Minimum checklist:
1. Base URL per hotel, `Accept: application/json`, your own User-Agent.
2. Both key headers on variables calls; keys from env, never logged.
3. Timeouts and retry with backoff on 429/5xx (never on 4xx).
4. 64-bit-safe JSON.
5. Batch helper that splits into chunks of 50 and checks each result's status.
6. Furni id conversion and the fixed level-up maths.
