"""Read-only smoke test for the Habbo WIRED Web API (stdlib only, no writes).

Checks that the hotel answers, then lists the room's variable names and its
global variables profile. Never PUT/PATCH/DELETEs anything.

Environment (put them in a gitignored .env, never in code):
    WIRED_ROOM_ID      room id with the "Variable Global Add-on: Web API" box
    WIRED_READ_KEY     the room's read key   -> header X-Wired-Read-Key
    WIRED_WRITE_KEY    not needed: per the spec GETs take only the read key
    WIRED_HOTEL_URL    default https://www.habbo.com  (sandbox: https://sandbox.habbo.com)

Usage:
    python wired_smoke.py            # ping + list variables + global profile
    python wired_smoke.py --ping     # only check the hotel answers
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT_S = 15


def call(path: str, headers: dict[str, str] | None = None) -> tuple[int, object]:
    base = os.environ.get("WIRED_HOTEL_URL", "https://www.habbo.com").rstrip("/")
    request = urllib.request.Request(
        f"{base}{path}",
        headers={"Accept": "application/json", "User-Agent": "wired-smoke/1.0", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, body[:200]


def main() -> int:
    status, _ = call("/api/public/ping")
    print(f"ping: HTTP {status}")
    if status != 200 or "--ping" in sys.argv:
        return 0 if status == 200 else 1

    room = os.environ.get("WIRED_ROOM_ID")
    read_key = os.environ.get("WIRED_READ_KEY")
    if not room or not read_key:
        print("set WIRED_ROOM_ID and WIRED_READ_KEY to test the variable endpoints")
        return 1
    headers = {"X-Wired-Read-Key": read_key}  # GETs need only the read key (spec)

    for path in (f"/api/public/rooms/{room}/variables", f"/api/public/rooms/{room}/variables_profile/global"):
        status, body = call(path, headers)
        print(f"GET {path}: HTTP {status}")
        print(json.dumps(body, indent=2)[:2000])  # values arrive as decimal strings
    return 0


if __name__ == "__main__":
    sys.exit(main())
