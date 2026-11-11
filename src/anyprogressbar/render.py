"""Renderers: what turns snapshots of a tree of bars into something to look at.

A bar knows nothing of terminals or notebooks. Its root hands a `Snapshot` to a renderer, at
most every `min_interval` seconds and at each start and end. So far there are two: nothing,
and log lines. The terminal line, the notebook's HTML and the widget come next.
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Protocol, TextIO

from anyprogressbar import format as fmt
from anyprogressbar.state import Snapshot, Status


class Renderer(Protocol):
    def update(self, root: Snapshot) -> None:
        """The tree changed (or a bar in it started or ended)."""

    def close(self, root: Snapshot) -> None:
        """The root ended; `root.status` says how."""


class NullRenderer:
    """Shows nothing."""

    def update(self, root: Snapshot) -> None:
        pass

    def close(self, root: Snapshot) -> None:
        pass


class LogRenderer:
    """Lines that are only ever added: for pipes, files and CI logs.

    A line every `interval` seconds while the work runs, and one when it ends. Work that is
    done within `delay` seconds prints nothing; work that fails or stops always says so.
    """

    def __init__(
        self, file: TextIO | None = None, *, interval: float = 5.0, delay: float = 2.0
    ) -> None:
        self._file = file
        self.interval = interval
        self.delay = delay
        self._last: dict[int, float] = {}  # root id -> its elapsed time at the last line

    def _write(self, line: str) -> None:
        file = self._file if self._file is not None else sys.stderr
        file.write(line + "\n")
        file.flush()

    def update(self, root: Snapshot) -> None:
        if root.status is not Status.RUNNING or root.elapsed < self.delay:
            return
        last = self._last.get(root.id)
        if last is None or root.elapsed - last >= self.interval:
            self._last[root.id] = root.elapsed
            self._write(running_line(root))

    def close(self, root: Snapshot) -> None:
        printed = self._last.pop(root.id, None) is not None
        if root.status is Status.DONE and not printed and root.elapsed < self.delay:
            return
        self._write(final_line(root))


def _name(bar: Snapshot) -> str:
    return bar.desc or "Progress"


def _position(bar: Snapshot) -> str:
    if bar.total is None:
        return f"{fmt.count(bar.n)} {bar.unit}"
    fraction = bar.fraction or 0.0
    return f"{fmt.count(bar.n)}/{fmt.count(bar.total)} ({100 * fraction:.0f}%)"


def _running_child(bar: Snapshot) -> Snapshot | None:
    """The deepest bar that is running under `bar`, following the last one at each level."""
    found = None
    while True:
        running = [c for c in bar.children if c.status is Status.RUNNING]
        if not running:
            return found
        found = bar = running[-1]


def running_line(root: Snapshot) -> str:
    parts = [f"{_name(root)}: {_position(root)}", f"{fmt.elapsed(root.elapsed)} elapsed"]
    if root.remaining is not None:
        parts.append(f"about {fmt.remaining(root.remaining)} left")
    elif root.total is None and root.rate is not None:
        parts.append(fmt.rate(root.rate, root.unit))
    parts.extend(f"{k}={v}" for k, v in root.metrics.items())
    line = ", ".join(parts)
    child = _running_child(root)
    if child is not None:
        line += f" | {_name(child)}: {_position(child)}"
    return line


def final_line(root: Snapshot) -> str:
    took = fmt.elapsed(root.elapsed)
    if root.status is Status.DONE:
        line = f"{_name(root)}: done, {fmt.count(root.n)} {root.unit} in {took}"
        if root.elapsed > 0 and root.n > 0:
            line += f" ({fmt.rate(root.n / root.elapsed, root.unit)})"
        return line
    line = f"{_name(root)}: {root.status.value} at {_position(root)} after {took}"
    return f"{line}: {root.message}" if root.message else line


ENV = "ANYPROGRESSBAR"
_named = {"off": NullRenderer, "log": LogRenderer}
_default: Renderer | None = None


def set_renderer(renderer: Renderer | str | None) -> None:
    """The renderer for bars that are given none: an object, a name ("log", "off"), or None
    to choose by the environment again."""
    global _default  # noqa: PLW0603
    if isinstance(renderer, str):
        if renderer not in _named:
            raise ValueError(f"unknown renderer {renderer!r}; one of {sorted(_named)}")
        renderer = _named[renderer]()
    _default = renderer


def default_renderer() -> Renderer:
    """`set_renderer`'s, else the one the `ANYPROGRESSBAR` variable names, else log lines."""
    if _default is not None:
        return _default
    name = os.environ.get(ENV, "").strip().lower()
    if name in _named:
        return _named[name]()
    if name:
        # a mistake in deployment configuration should not stop the work
        warnings.warn(
            f"{ENV}={name!r} is not a renderer (one of {sorted(_named)}); ignored", stacklevel=2
        )
    return LogRenderer()
