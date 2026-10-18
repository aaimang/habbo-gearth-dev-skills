"""Level Up add-on maths: read a raw XP variable, get level / progress / remaining.

Port of the official ``level-upper.ts`` snippet (see ../assets/), WITH the
``LinearLevelUpper.max_xp`` fix: ``(max_level - 1) * step_size``. Both the original
TS snippet and the ``wired-api-python`` wrapper (0.1.4) still use
``max_level * step_size``, which is wrong.

Python ints are arbitrary precision, so 64-bit variable values are exact. Places
where the server uses floating point (percentages, interpolation, exponential
curves) mirror the JS ``Number`` maths so results match the game.

    >>> lin = LevelUpper.linear(step_size=100, max_level=10)
    >>> lin.max_xp(), lin.current_level(0), lin.current_level(250), lin.progress(250)
    (900, 1, 3, 50)
    >>> lin.current_level(10**12), lin.is_maxed(900), lin.xp_remaining(250)
    (10, True, 50)
    >>> curve = LevelUpper.interpolate({2: 100, 5: 400, 10: 1400})
    >>> curve.current_level(250), curve.max_level(), curve.max_xp()
    (3, 10, 1400)
    >>> exp = LevelUpper.exponential(initial_xp=100, strength=50, max_level=20)
    >>> exp.current_level(0), exp.current_level(100), exp.current_level(250)
    (1, 2, 3)

Run ``python level_upper.py`` to execute the self-test.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping


class LevelUpper(ABC):
    """Common interface (same methods as the TS ``LevelUpperConfig``)."""

    @staticmethod
    def linear(step_size: int, max_level: int) -> LevelUpper:
        return LinearLevelUpper(step_size, max_level)

    @staticmethod
    def interpolate(level_to_xp: Mapping[int, int]) -> LevelUpper:
        return InterpolateLevelUpper(level_to_xp)

    @staticmethod
    def exponential(initial_xp: int, strength: int, max_level: int) -> LevelUpper:
        return ExponentialLevelUpper(initial_xp, strength, max_level)

    def bounded_value(self, xp: int) -> int:
        if xp < 0:
            return 0
        return min(xp, self.max_xp())

    @abstractmethod
    def current_level(self, xp: int) -> int: ...
    @abstractmethod
    def total_xp_required(self, xp: int) -> int: ...
    @abstractmethod
    def progress(self, xp: int) -> int: ...
    @abstractmethod
    def progress_percentage(self, xp: int) -> int: ...
    @abstractmethod
    def xp_remaining(self, xp: int) -> int: ...
    @abstractmethod
    def is_maxed(self, xp: int) -> bool: ...
    @abstractmethod
    def max_level(self) -> int: ...
    @abstractmethod
    def max_xp(self) -> int: ...


class LinearLevelUpper(LevelUpper):
    def __init__(self, step_size: int, max_level: int) -> None:
        if step_size <= 0 or max_level < 1:
            raise ValueError("step_size must be > 0 and max_level >= 1")
        self._step = step_size
        self._max_level = max_level

    def current_level(self, xp: int) -> int:
        return min(self._max_level, 1 + self.bounded_value(xp) // self._step)

    def total_xp_required(self, xp: int) -> int:
        return 0 if self.is_maxed(xp) else self._step

    def progress(self, xp: int) -> int:
        return 0 if self.is_maxed(xp) else self.bounded_value(xp) % self._step

    def progress_percentage(self, xp: int) -> int:
        if self.is_maxed(xp):
            return 0
        return math.floor(float(self.progress(xp)) / float(self._step) * 100)

    def xp_remaining(self, xp: int) -> int:
        bounded = self.bounded_value(xp)
        return 0 if self.is_maxed(bounded) else self._step - bounded % self._step

    def is_maxed(self, xp: int) -> bool:
        return self.current_level(xp) >= self._max_level

    def max_level(self) -> int:
        return self._max_level

    def max_xp(self) -> int:
        return (self._max_level - 1) * self._step  # the fix


class InterpolateLevelUpper(LevelUpper):
    """Levels between configured (level -> xp) points are spread evenly."""

    def __init__(self, level_to_xp: Mapping[int, int]) -> None:
        self._points = sorted(
            ({"level": int(level), "xp": int(xp)} for level, xp in level_to_xp.items()),
            key=lambda p: p["xp"],
        )

    def current_level(self, xp: int) -> int:
        return self._info(xp)["current_level"]

    def total_xp_required(self, xp: int) -> int:
        info = self._info(xp)
        return info["next_level_xp"] - info["current_level_xp"]

    def progress(self, xp: int) -> int:
        info = self._info(xp)
        return info["current_xp"] - info["current_level_xp"]

    def progress_percentage(self, xp: int) -> int:
        info = self._info(xp)
        total = info["next_level_xp"] - info["current_level_xp"]
        if total == 0:
            return 0
        return math.floor(float(info["current_xp"] - info["current_level_xp"]) / float(total) * 100)

    def xp_remaining(self, xp: int) -> int:
        info = self._info(xp)
        return info["next_level_xp"] - info["current_xp"]

    def is_maxed(self, xp: int) -> bool:
        return self._info(xp)["is_maxed"]

    def max_level(self) -> int:
        return self._info(self.max_xp())["current_level"]

    def max_xp(self) -> int:
        return self._points[-1]["xp"] if self._points else 0

    def _info(self, xp: int) -> dict:
        if not self._points:
            return dict(current_level=1, current_level_xp=0, current_xp=0, next_level_xp=0, is_maxed=True)
        bounded = self.bounded_value(xp)
        last = self._points[-1]
        if bounded >= last["xp"]:
            return dict(
                current_level=last["level"],
                current_level_xp=last["xp"],
                current_xp=last["xp"],
                next_level_xp=last["xp"],
                is_maxed=True,
            )
        floor_pt = {"level": 1, "xp": 0}
        ceil_pt = self._points[0]
        for entry in self._points:
            if entry["xp"] <= bounded:
                floor_pt = entry
                continue
            ceil_pt = entry
            break

        level_diff = ceil_pt["level"] - floor_pt["level"]
        xp_per_level = float(ceil_pt["xp"] - floor_pt["xp"]) / float(level_diff)
        steps = int(min(max(math.floor(float(bounded - floor_pt["xp"]) / xp_per_level), 0), level_diff - 1))

        current_level = floor_pt["level"] + steps
        current_level_xp = floor_pt["xp"] + math.floor(xp_per_level * steps)
        if steps == level_diff - 1:
            next_level_xp = ceil_pt["xp"]
        else:
            next_level_xp = floor_pt["xp"] + math.floor(xp_per_level * (steps + 1))
            if bounded >= next_level_xp:
                steps += 1
                current_level = floor_pt["level"] + steps
                current_level_xp = floor_pt["xp"] + math.floor(xp_per_level * steps)
                next_level_xp = (
                    ceil_pt["xp"]
                    if steps == level_diff
                    else floor_pt["xp"] + math.floor(xp_per_level * (steps + 1))
                )
        return dict(
            current_level=current_level,
            current_level_xp=current_level_xp,
            current_xp=bounded,
            next_level_xp=next_level_xp,
            is_maxed=False,
        )


class ExponentialLevelUpper(LevelUpper):
    """XP per level grows by ``strength`` percent each level."""

    def __init__(self, initial_xp: int, strength: int, max_level: int) -> None:
        if strength <= 0 or initial_xp <= 0 or max_level < 1:
            raise ValueError("initial_xp and strength must be > 0, max_level >= 1")
        self._initial = initial_xp
        self._s = float(strength) / 100
        self._max_level = max_level
        self._max_xp = 0  # xp_for_level reads it only for level > max_level
        self._max_xp = self._xp_for_level(max_level)

    def current_level(self, xp: int) -> int:
        bounded = self.bounded_value(xp)
        if bounded <= 0:
            return 1
        level = (
            math.floor(math.log(float(bounded) * self._s / float(self._initial) + 1) / math.log(1 + self._s))
            + 1
        )
        if level > self._max_level:
            return self._max_level
        if level < 1:
            return 1
        if bounded < self._xp_for_level(level):
            return level - 1 if level > 1 else 1
        if bounded >= self._xp_for_level(level + 1):
            return min(level + 1, self._max_level)
        return level

    def total_xp_required(self, xp: int) -> int:
        if self.is_maxed(xp):
            return 0
        level = self.current_level(xp)
        return self._xp_for_level(level + 1) - self._xp_for_level(level)

    def progress(self, xp: int) -> int:
        bounded = self.bounded_value(xp)
        if self.is_maxed(bounded):
            return 0
        return bounded - self._xp_for_level(self.current_level(bounded))

    def progress_percentage(self, xp: int) -> int:
        bounded = self.bounded_value(xp)
        if self.is_maxed(bounded):
            return 0
        level = self.current_level(bounded)
        lo, hi = self._xp_for_level(level), self._xp_for_level(level + 1)
        if lo == hi:
            return 100
        return math.floor(float(bounded - lo) / float(hi - lo) * 100)

    def xp_remaining(self, xp: int) -> int:
        bounded = self.bounded_value(xp)
        if self.is_maxed(bounded):
            return 0
        return self._xp_for_level(self.current_level(bounded) + 1) - bounded

    def is_maxed(self, xp: int) -> bool:
        return self.current_level(xp) >= self._max_level

    def max_level(self) -> int:
        return self._max_level

    def max_xp(self) -> int:
        return self._max_xp

    def _xp_for_level(self, level: int) -> int:
        if level < 1:
            return 0
        if level > self._max_level:
            return self._max_xp
        return math.floor(float(self._initial) * ((math.pow(1 + self._s, level - 1) - 1 + 1e-9) / self._s))


if __name__ == "__main__":
    import doctest

    failures, _ = doctest.testmod()
    print("level_upper: ok" if not failures else f"level_upper: {failures} failures")
