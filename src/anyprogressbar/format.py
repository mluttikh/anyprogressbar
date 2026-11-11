"""Numbers and times as text."""

from __future__ import annotations

from typing import Any


def count(value: float) -> str:
    """A count without a needless decimal: 3, 2.5, 1200."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3g}"


def elapsed(seconds: float) -> str:
    """Time passed, exact to the second: 00:42, 12:05, 1:02:03."""
    s = max(0, int(seconds))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def remaining(seconds: float) -> str:
    """Time left, coarser the further away it is: 8 s, 40 s, 3 min, 2 h 15 min."""
    if seconds < 20:
        return f"{max(1, round(seconds))} s"
    if seconds < 55:
        return f"{5 * round(seconds / 5)} s"
    if seconds < 3570:
        return f"{max(1, round(seconds / 60))} min"
    quarters = round(seconds / 900)
    h, q = divmod(quarters, 4)
    return f"{h} h {15 * q:02d} min" if q else f"{h} h"


def rate(per_second: float, unit: str) -> str:
    """A rate in the unit that keeps the number readable: 227 it/s, 2.4 it/min, 1.5 it/h."""
    for scale, per in ((1, "s"), (60, "min"), (3600, "h")):
        value = per_second * scale
        if value >= 1 or per == "h":
            break
    digits = f"{value:.0f}" if value >= 100 else f"{value:.3g}"
    return f"{digits} {unit}/{per}"


def metric(value: Any) -> str:
    """A metric beside the bar: floats short, everything else as it prints."""
    if isinstance(value, float):
        return f"{value:.3g}"
    return str(value)
