"""Convert furni ids between the game (WIRED/packets) and the Habbo Web API.

Port of the official ``furni-id-conversion.ts`` snippet (see ../assets/).

In game, wall items have NEGATIVE ids and BC (Builders Club) items are offset by
``0x7FFFFFFF - 0xFFFF``. The API uses plain positive ids plus a target kind:
``furni``, ``furni-bc``, ``wall-items`` or ``wall-items-bc``.

    >>> to_furni_id(123)
    ('furni', 123)
    >>> to_furni_id(-123)
    ('wall-items', 123)
    >>> to_furni_id(MIN_CLUB_FURNI_ID + 5)
    ('furni-bc', 5)
    >>> to_furni_id(-(MIN_CLUB_FURNI_ID + 5))
    ('wall-items-bc', 5)
    >>> from_furni_id('wall-items-bc', 5) == -(MIN_CLUB_FURNI_ID + 5)
    True

Run ``python furni_ids.py`` to execute the self-test.
"""

from __future__ import annotations

from typing import Literal

FurniKind = Literal["furni", "furni-bc", "wall-items", "wall-items-bc"]

MAX_CLUB_FURNI_ID = 0x7FFFFFFF
MIN_CLUB_FURNI_ID = MAX_CLUB_FURNI_ID - 0xFFFF  # 2147418112


def to_furni_id(game_furni_id: int) -> tuple[FurniKind, int]:
    """Game id -> (API target kind, API id)."""
    is_wall = game_furni_id < 0
    normalized = -game_furni_id if is_wall else game_furni_id
    if normalized >= MIN_CLUB_FURNI_ID:
        local = normalized - MIN_CLUB_FURNI_ID
        return ("wall-items-bc" if is_wall else "furni-bc"), local
    return ("wall-items" if is_wall else "furni"), normalized


def from_furni_id(kind: FurniKind, api_id: int) -> int:
    """(API target kind, API id) -> game id."""
    if kind not in ("furni", "furni-bc", "wall-items", "wall-items-bc"):
        raise ValueError(f"unknown furni kind {kind!r}")
    base = api_id + MIN_CLUB_FURNI_ID if kind.endswith("-bc") else api_id
    return -base if kind.startswith("wall-items") else base


if __name__ == "__main__":
    import doctest

    for game_id in (1, 987654321, -1, -987654321, MIN_CLUB_FURNI_ID, -MAX_CLUB_FURNI_ID):
        assert from_furni_id(*to_furni_id(game_id)) == game_id, game_id
    failures, _ = doctest.testmod()
    print("furni_ids: ok" if not failures else f"furni_ids: {failures} failures")
