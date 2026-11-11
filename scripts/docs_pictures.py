"""Pictures of bars for the user documentation, made by running the pages' examples.

The examples in the pages run while the documentation is built (markdown-exec). Hidden lines
swap in a clock that `time.sleep` moves, so they run at once and say the same each time, and
a renderer that keeps every picture. A page's example looks like this in its source:

    ```python exec="on" source="above" html="true"
    import time
    from anyprogressbar import progress
    from docs_pictures import fake, show_html  # markdown-exec: hide
    progress, time = fake(progress)  # markdown-exec: hide

    for row in progress(range(60), "Loading", unit="rows"):
        time.sleep(0.05)
    print(show_html())  # markdown-exec: hide
    ```

`show_html()`, `show_terminal()`, `show_log()` and `show_replay()` show the bars that ended
since the last picture: as the notebook shows them, as a terminal does, as log lines, or
played again in the page through the widget's own code (`docs/user/assets/replay.js`).
"""

from __future__ import annotations

import functools
import html as escape
import io
import json
import types
from dataclasses import dataclass, field, replace
from typing import Any

from anyprogressbar import LogRenderer, Snapshot, Status, set_renderer
from anyprogressbar.notebook import to_html
from anyprogressbar.terminal import lines

_SGR = {"36": "running", "32": "done", "31": "failed", "33": "stopped", "2": "pending"}


class Clock:
    """Time that passes only when something sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)


@dataclass
class Run:
    """One bar of its own: every picture it was given, and the last."""

    pictures: list[Snapshot] = field(default_factory=list)
    last: Snapshot | None = None


class Keeper:
    """A renderer that keeps every picture, per bar of its own."""

    def __init__(self) -> None:
        self.runs: dict[int, Run] = {}
        self.ended: list[Run] = []

    def update(self, root: Snapshot) -> None:
        self.runs.setdefault(root.id, Run()).pictures.append(root)

    def close(self, root: Snapshot) -> None:
        run = self.runs.pop(root.id, Run())
        run.pictures.append(root)
        run.last = root
        self.ended.append(run)

    def take(self) -> list[Run]:
        ended, self.ended = self.ended, []
        return ended


_keeper = Keeper()
_clock = Clock()


def fake(progress: Any) -> tuple[Any, types.SimpleNamespace]:
    """`progress` on the fake clock, and a `time` module whose `sleep` moves it."""
    set_renderer(_keeper)
    _keeper.take()  # what an earlier page left
    clocked = functools.partial(progress, clock=_clock)
    clock = types.SimpleNamespace(
        sleep=_clock.sleep, perf_counter=_clock, monotonic=_clock, time=_clock
    )
    return clocked, clock


def _later(bar: Snapshot, dt: float) -> Snapshot:
    """The bar `dt` seconds after the picture, as a clock that ticks by itself shows it (the
    terminal's thread, the widget): running clocks move on, nothing else does."""
    children = tuple(_later(child, dt) for child in bar.children)
    if bar.status is not Status.RUNNING:
        return replace(bar, children=children)
    return replace(
        bar,
        children=children,
        elapsed=bar.elapsed + dt,
        since_progress=bar.since_progress + dt,
        remaining=None if bar.remaining is None else max(0.0, bar.remaining - dt),
    )


def _at(run: Run, at: float | None) -> Snapshot | None:
    """The bar `at` seconds into the run (the last picture before then, with its clocks moved
    on), or as it ended."""
    if at is None or not run.pictures:
        return run.last
    before = [p for p in run.pictures if p.elapsed <= at] or run.pictures[:1]
    picture = before[-1]
    return _later(picture, at - picture.elapsed)


def _shown(run: Run, delay: float = 0.5) -> bool:
    """Work done within the delay is never shown."""
    last = run.last
    return last is None or not (last.status is Status.DONE and last.elapsed < delay)


def show_html(at: float | None = None) -> str:
    """The bars that ended since the last picture, as a notebook shows them: at the end, or
    as they were `at` seconds in."""
    parts = []
    for run in _keeper.take():
        picture = _at(run, at)
        if picture is not None and _shown(run):
            parts.append(f'<div class="apb-picture">{to_html(picture)}</div>')
    return "".join(parts)


def show_terminal(at: float | None = None, columns: int = 76) -> str:
    """The same as a terminal shows them, coloured as the terminal colours them."""
    rows = []
    for run in _keeper.take():
        picture = _at(run, at)
        if picture is None or not _shown(run):
            continue
        for segments in lines(picture, columns):
            row = ""
            for text, style in segments:
                safe = escape.escape(text)
                kind = _SGR.get(style)
                row += f'<span class="apb-t-{kind}">{safe}</span>' if kind else safe
            rows.append(row.rstrip())
    return f'<pre class="apb-terminal"><code>{"\n".join(rows)}</code></pre>' if rows else ""


def show_log(interval: float = 5.0, delay: float = 2.0) -> str:
    """The same as log lines, as a CI job or a file would get them."""
    out = io.StringIO()
    renderer = LogRenderer(out, interval=interval, delay=delay)
    for run in _keeper.take():
        for picture in run.pictures:
            if picture is run.last:
                renderer.close(picture)
            else:
                renderer.update(picture)
    text = escape.escape(out.getvalue().rstrip("\n"))
    return f'<pre class="apb-terminal"><code>{text}</code></pre>' if text else ""


def show_replay(speed: float = 1.0) -> str:
    """The bars played again in the page, through the widget's own code, with the pictures
    at the times the kernel sent them."""
    parts = []
    for run in _keeper.take():
        if not run.pictures:
            continue
        frames = [[p.elapsed / speed, p.as_dict()] for p in run.pictures]
        data = escape.escape(json.dumps(frames, separators=(",", ":")))
        fallback = to_html(run.last) if run.last is not None else ""
        parts.append(f'<div class="apb-replay" data-frames="{data}">{fallback}</div>')
    return "".join(parts)
