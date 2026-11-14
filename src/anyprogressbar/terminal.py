"""The terminal renderer: lines that are redrawn in place, on a terminal that allows it.

One instance draws every tree that is live on its stream, as one frame. A frame is built
whole and written at once, inside a synchronized update where the terminal has those. A
thread redraws ten times a second, asking each root for a fresh picture, so that clocks
tick and a stall shows while the loop itself is busy with one slow item.

A finished root's last line stays in the scrollback; work that is done within `delay`
seconds is never drawn at all.

While bars are live, `sys.stdout` and `sys.stderr` (where they are terminals) are replaced
by `Redirect`, and logging handlers that write to them are pointed at it: a line that is
printed or logged then goes above the bars instead of through them. A line that is not
finished and is flushed (a prompt for `input()`) hands the terminal back until the line is
finished. (Decision 0005.)
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import sys
import threading
import time
import unicodedata
import weakref
from collections.abc import Callable, Iterable
from typing import Any

from anyprogressbar import format as fmt
from anyprogressbar.render import Stream
from anyprogressbar.state import Snapshot, Status

ESC = "\x1b"
_HIDE, _SHOW = f"{ESC}[?25l", f"{ESC}[?25h"
_SYNC_ON, _SYNC_OFF = f"{ESC}[?2026h", f"{ESC}[?2026l"
_EIGHTHS = " ▏▎▍▌▋▊▉█"
# the 16 colours, so that contrast is the terminal theme's to decide
_COLOR = {
    Status.RUNNING: "36",
    Status.DONE: "32",
    Status.FAILED: "31",
    Status.STOPPED: "33",
    Status.PENDING: "2",
}

Segment = tuple[str, str]  # text, and its SGR code ("" for none)


def cells(text: str) -> int:
    """The columns `text` takes: wide characters two, combining marks none."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in "WF" else 1
    return width


def clip(text: str, width: int) -> str:
    """`text` cut to `width` columns, ending in an ellipsis when cut."""
    if cells(text) <= width:
        return text
    out, used = [], 0
    for ch in text:
        w = cells(ch)
        if used + w > width - 1:
            break
        out.append(ch)
        used += w
    return "".join(out) + "…" if width >= 1 else ""


def fill(fraction: float, width: int, *, ascii: bool) -> tuple[str, str]:
    """The filled and the empty part of a bar `width` columns wide."""
    if ascii:
        full = round(fraction * width)
        return "#" * full, "-" * (width - full)
    full, part = divmod(round(fraction * width * 8), 8)
    filled = "█" * full + (_EIGHTHS[part] if part else "")
    return filled, " " * (width - len(filled))


def bounce(elapsed: float, width: int, *, ascii: bool) -> tuple[str, str, str]:
    """A block that runs back and forth, for work without a total: before, block, after."""
    size = min(3, width)
    span = width - size
    step = int(elapsed * 12) % (2 * span) if span > 0 else 0
    at = step if step <= span else 2 * span - step
    return " " * at, ("#" if ascii else "█") * size, " " * (span - at)


def stalled(bar: Snapshot) -> bool:
    """Nothing for long enough to say so: ten seconds, and five times what a unit took on
    average until then (thirty seconds when no unit is done yet)."""
    if bar.status is not Status.RUNNING:
        return False
    quiet = _quiet(bar)  # a bar whose child moves is not stalled
    if bar.n <= 0:
        return quiet >= 30
    per_unit = (bar.elapsed - bar.since_progress) / bar.n
    return quiet >= max(10.0, 5 * per_unit)


def _quiet(bar: Snapshot) -> float:
    """Seconds since the bar, or anything running under it, last moved."""
    running = [c for c in bar.children if c.status is Status.RUNNING]
    return min([bar.since_progress, *(_quiet(c) for c in running)])


def stats(bar: Snapshot) -> str:
    """The numbers beside a bar: where it is, how long it took or will take, how it ended."""
    total = bar.total
    position = (
        f"{fmt.count(bar.n)}/{fmt.count(total)}"
        if total is not None
        else f"{fmt.count(bar.n)} {bar.unit}"
    )
    took = fmt.elapsed(bar.elapsed)
    if bar.status is Status.DONE:
        parts = [position, f"done in {took}"]
        if bar.elapsed > 0 and bar.n > 0:
            parts.append(fmt.rate(bar.n / bar.elapsed, bar.unit))
    elif bar.status.finished:
        end = f"{bar.status.value} after {took}"
        parts = [position, f"{end}: {bar.message}" if bar.message else end]
    else:
        parts = [position, took]
        if stalled(bar):  # then the rate and the time remaining say nothing true
            parts.append(f"no progress for {fmt.remaining(_quiet(bar))}")
        else:
            if bar.remaining is not None:
                parts.append(f"about {fmt.remaining(bar.remaining)} left")
            if bar.rate is not None:
                parts.append(fmt.rate(bar.rate, bar.unit))
    parts.extend(f"{k}={v}" for k, v in bar.metrics.items())
    return " · ".join(parts)


def line(
    bar: Snapshot, columns: int, *, depth: int = 0, ascii: bool = False, name_width: int = 0
) -> list[Segment]:
    """One bar as segments that fit in `columns`: name, percentage, bar, numbers."""
    color = _COLOR[bar.status]
    numbers = stats(bar)
    if ascii:
        numbers = numbers.replace(" · ", ", ")
    fraction = bar.fraction
    percent = f"{100 * fraction:3.0f}%" if fraction is not None else ""
    name = "  " * depth + (bar.desc or "Progress")
    # The bar's width follows the terminal's only, so that it does not change as the numbers
    # beside it grow and shrink; the name gets at most a third, the numbers what is left.
    name = clip(name, max(8, columns // 3))
    name += " " * (name_width - cells(name))  # bars of one tree start in one column
    width = min(30, columns // 4)
    segments: list[Segment] = [(name, "1")]
    if percent:
        segments += [(" ", ""), (percent, "")]
    used = cells(name) + cells(percent) + cells(numbers) + 2
    if bar.status in (Status.FAILED, Status.STOPPED) and used + width + 3 > columns:
        width = 0  # the reason it ended matters more than the bar
    if width >= 6:
        left, right = ("[", "]") if ascii else ("▕", "▏")
        if fraction is None and not bar.status.finished:
            before, block, after = bounce(bar.elapsed, width, ascii=ascii)
            segments += [(" " + left + before, "2"), (block, color), (after + right, "2")]
        else:
            filled, empty = fill(1.0 if fraction is None else fraction, width, ascii=ascii)
            segments += [(" " + left, "2"), (filled, color), (empty + right, "2")]
    segments += [(" ", ""), (numbers, color if bar.status.finished else "2")]
    return _fit(segments, columns)


def _fit(segments: list[Segment], columns: int) -> list[Segment]:
    out: list[Segment] = []
    room = columns
    for text, style in segments:
        if room <= 0:
            break
        clipped = clip(text, room)
        out.append((clipped, style))
        room -= cells(clipped)
    return out


def lines(root: Snapshot, columns: int, *, ascii: bool = False) -> list[list[Segment]]:
    """A tree as lines: the root, then what runs, failed or stopped under it, indented."""
    bars: list[tuple[Snapshot, int]] = []

    def walk(bar: Snapshot, depth: int) -> None:
        bars.append((bar, depth))
        for child in bar.children:
            if child.status is not Status.PENDING:
                walk(child, depth + 1)

    walk(root, 0)
    limit = max(8, columns // 3)
    name_width = max(min(limit, cells("  " * d + (b.desc or "Progress"))) for b, d in bars)
    return [line(b, columns, depth=d, ascii=ascii, name_width=name_width) for b, d in bars]


def _osc_progress() -> bool:
    """Terminals known to show OSC 9;4 progress in the tab or the taskbar. Not iTerm2, where
    OSC 9 has long meant a notification."""
    env = os.environ
    return bool(
        env.get("WT_SESSION")
        or env.get("ConEmuANSI") == "ON"
        or env.get("TERM_PROGRAM", "").lower() == "ghostty"
    )


class Redirect:
    """A text stream that hands whole lines to a renderer while it is active, and passes
    everything straight through otherwise. Everything else is the stream it stands for."""

    def __init__(self, original: Any, renderer: TerminalRenderer) -> None:
        self._original = original
        self._renderer = renderer
        self._local = threading.local()  # .busy: in the renderer already; .partial: a line
        self.active = True

    def write(self, text: str) -> int:
        if not self.active or getattr(self._local, "busy", False):
            return self._original.write(text)
        self._local.busy = True
        try:
            # each thread's unfinished line is its own: lines from two threads stay whole
            *lines, self._local.partial = (self._partial + text).split("\n")
            for line in lines:
                self._renderer.print_line(line, self._original)
        finally:
            self._local.busy = False
        return len(text)

    @property
    def _partial(self) -> str:
        return getattr(self._local, "partial", "")

    def writelines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        """A line that is flushed before it is finished is meant to be seen now."""
        if self.active and self._partial and not getattr(self._local, "busy", False):
            self._local.busy = True
            try:
                self._renderer.print_partial(self._partial, self._original)
            finally:
                self._local.busy = False
            self._local.partial = ""
        self._original.flush()

    def release(self) -> None:
        """Stop handing lines over; what is left of a line goes out as it is."""
        self.active = False
        if self._partial:  # this thread's; another thread's is lost with its line
            self._original.write(self._partial)
            self._local.partial = ""
        with contextlib.suppress(Exception):
            self._original.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


def unwrap(stream: Any) -> Any:
    """The stream a `Redirect` stands for; any other stream as it is."""
    while isinstance(stream, Redirect):
        stream = stream._original
    return stream


def _is_tty(stream: Any) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _stream_handlers() -> list[logging.StreamHandler]:
    loggers: list[Any] = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    return [
        handler
        for logger in loggers
        if isinstance(logger, logging.Logger)
        for handler in logger.handlers
        if type(handler) is logging.StreamHandler  # not files, sockets or other subclasses
    ]


class TerminalRenderer:
    """Draws bars in place on a terminal.

    On a stream that is not a terminal (a notebook's output, when this renderer is chosen
    there) only a carriage return can be relied on, and escape sequences other than colours
    show as text. There the renderer redraws one line, the first tree's top bar, by going
    back and writing over it, spaces where the old line was longer; it leaves out the tab
    progress, synchronized output and the hidden cursor; and at the end writes each finished
    tree whole, as on a terminal. JupyterLab writes over the old line character by character
    before it takes the escape sequences out, colours too: so the spaces cover the old line
    as it was written, not as it was seen.

    Args:
        file: The stream; standard error by default (looked up at each write).
        interval: Seconds between two redraws by the thread that keeps the clock ticking.
        delay: Bars are first drawn when they have run this long; work done sooner is never
            drawn.
        ascii: `#` and `-` instead of block characters. By default where the stream's
            encoding has no block characters.
        color: Colour by status. By default unless `NO_COLOR` is set.
        threaded: False draws only when a bar hands over a picture (for tests).
        columns: The width to draw in. By default the terminal's, asked at each draw.
        redirect: While bars are live, send what is printed or logged to the terminal above
            them.
    """

    def __init__(
        self,
        file: Stream | None = None,
        *,
        interval: float = 0.1,
        delay: float = 0.5,
        ascii: bool | None = None,
        color: bool | None = None,
        threaded: bool = True,
        columns: int | None = None,
        redirect: bool = True,
    ) -> None:
        self._file = file
        self.interval = interval
        self.delay = delay
        self._ascii = ascii
        self._color = color if color is not None else not os.environ.get("NO_COLOR")
        self._threaded = threaded
        self._columns = columns
        self._osc = _osc_progress()
        self._lock = threading.RLock()
        self._redirect = redirect
        self._redirects: dict[str, Redirect] = {}  # "stdout"/"stderr" -> what replaced it
        self._handlers: list[tuple[logging.StreamHandler, Any]] = []  # and their streams
        self._suspended = False  # an unfinished line of someone else's is on the screen
        self._repainted = 0.0  # when printed lines last let the bars be drawn again
        self._live: dict[int, Snapshot] = {}
        self._sources: dict[int, weakref.WeakMethod] = {}
        self._drawn: set[int] = set()  # roots that have been on screen
        self._height = 0  # lines of the frame now on screen
        self._frame = ""
        self._covers = 0  # on a stream that is not a terminal: the length of its line
        self._hidden = False
        self._thread: threading.Thread | None = None
        atexit.register(self._restore)

    # -- the stream ------------------------------------------------------------------------

    @property
    def file(self) -> Stream:
        return unwrap(self._file if self._file is not None else sys.stderr)

    def _use_ascii(self) -> bool:
        if self._ascii is None:
            try:
                "▏█…·".encode(getattr(self.file, "encoding", None) or "ascii")
                self._ascii = False
            except (UnicodeError, LookupError):
                self._ascii = True
        return self._ascii

    def _width(self) -> int:
        if self._columns is not None:
            return self._columns
        try:
            # a pseudo-terminal that was never given a size reports 0 columns
            return os.get_terminal_size(self.file.fileno()).columns or 80  # ty: ignore[missing-attribute]
        except (OSError, ValueError, AttributeError):
            return 80

    def _styled(self, segments: list[Segment]) -> str:
        if not self._color:
            return "".join(text for text, _ in segments)
        return "".join(
            f"{ESC}[{style}m{text}{ESC}[0m" if style else text for text, style in segments
        )

    # -- the renderer's two methods, and the bar's way to be asked -------------------------

    def attach(self, root_id: int, source: Callable[[], Snapshot]) -> None:
        """A root offers a way to ask for its picture, which the thread uses."""
        with self._lock:
            self._sources[root_id] = weakref.WeakMethod(source)

    def update(self, root: Snapshot) -> None:
        with self._lock:
            if not self._live and self._redirect:
                self._take_streams()
            self._live[root.id] = root
            if not self._threaded:
                self._paint()
            elif self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, name="anyprogressbar", daemon=True
                )
                self._thread.start()

    def close(self, root: Snapshot) -> None:
        with self._lock:
            self._live.pop(root.id, None)
            self._sources.pop(root.id, None)
            shown = root.id in self._drawn
            self._drawn.discard(root.id)
            quick = root.status is Status.DONE and not shown and root.elapsed < self.delay
            keep = root.leave or root.status is not Status.DONE
            last = (
                [] if quick or not keep else lines(root, self._width() - 1, ascii=self._use_ascii())
            )
            self._paint(above=[self._styled(segments) for segments in last])
            if not self._live:
                self._give_streams()

    def write(self, text: str, file: Stream | None = None) -> None:
        """Print `text` above the bars (to standard output by default)."""
        target = unwrap(file if file is not None else sys.stdout)
        for line in text.split("\n"):
            self.print_line(line, target)

    def print_line(self, line: str, target: Stream) -> None:
        """A finished line, for `target`, above the bars. The bars come back at once after a
        line on its own; during a burst of lines at most every half `interval`, and the
        thread draws them again after the burst."""
        with self._lock:
            if self._suspended:  # the rest of a line that is on the screen already
                self._suspended = False
            else:
                self._erase()
            target.write(line + "\n")
            target.flush()
            now = time.monotonic()
            if not self._threaded or now - self._repainted >= self.interval / 2:
                self._repainted = now
                self._paint(force=True)

    def print_partial(self, text: str, target: Stream) -> None:
        """An unfinished line that is to be seen now (a prompt): the bars make way until the
        line is finished."""
        with self._lock:
            if not self._suspended:
                self._erase()
                self._suspended = True
            target.write(text)
            target.flush()

    # -- standard output, standard error and logging ---------------------------------------

    def _take_streams(self) -> None:
        """Put a `Redirect` in place of each standard stream that is a terminal (a stream
        that goes to a file or a pipe cannot spoil the bars), and of the renderer's own."""
        own = self.file
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if isinstance(stream, Redirect) or not (stream is own or _is_tty(stream)):
                continue
            redirect = Redirect(stream, self)
            setattr(sys, name, redirect)
            self._redirects[name] = redirect
        originals = {id(r._original): r for r in self._redirects.values()}
        for handler in _stream_handlers():
            redirect = originals.get(id(handler.stream))
            if redirect is not None:
                self._handlers.append((handler, handler.stream))
                handler.stream = redirect  # not setStream: that flushes, under its lock

    def _give_streams(self) -> None:
        """Put back what was replaced, where nothing else has replaced it since. A
        `Redirect` that is still held somewhere passes everything through from now on."""
        if self._suspended:
            self.file.write("\n")
            self._suspended = False
        for name, redirect in self._redirects.items():
            redirect.release()
            if getattr(sys, name) is redirect:
                setattr(sys, name, redirect._original)
        for handler, stream in self._handlers:
            if isinstance(handler.stream, Redirect):
                handler.stream = stream
        self._redirects.clear()
        self._handlers.clear()

    # -- drawing ---------------------------------------------------------------------------

    def _run(self) -> None:
        while True:
            threading.Event().wait(self.interval)
            with self._lock:
                if not self._live:
                    self._thread = None
                    return
                sources = dict(self._sources)
            # ask outside the lock: a bar holds its own lock when it calls update()
            fresh = {}
            for root_id, ref in sources.items():
                source = ref()
                if source is not None:
                    with contextlib.suppress(Exception):
                        fresh[root_id] = source()
            with self._lock:
                for root_id, snapshot in fresh.items():
                    if root_id in self._live and snapshot.status is Status.RUNNING:
                        self._live[root_id] = snapshot
                self._paint()

    def _back(self, terminal: bool) -> str:
        """To the start of the frame, with the frame gone."""
        if not terminal:  # one line, written over
            return f"\r{' ' * self._covers}\r"
        up = f"{ESC}[{self._height - 1}A" if self._height > 1 else ""
        return f"\r{up}{ESC}[J"

    def _erase(self) -> None:
        if self._height:
            self.file.write(self._back(_is_tty(self.file)))
            self.file.flush()
            self._height = 0
            self._frame = ""

    def _paint(self, above: list[str] | None = None, *, force: bool = False) -> None:
        """Redraw the frame; `above` are lines to leave in the scrollback over it. `force`:
        also when the frame did not change (it was erased)."""
        if self._suspended:
            if not above:
                return
            self.file.write("\n")  # the bars' own lines go under the unfinished one
            self._suspended = False
        stream = self.file
        terminal = _is_tty(stream)
        columns = self._width() - 1  # the last column is left free: no terminal wraps then
        ascii = self._use_ascii()
        drawn: list[list[Segment]] = []
        for root in self._live.values():
            if root.id in self._drawn or root.elapsed >= self.delay:
                self._drawn.add(root.id)
                drawn += lines(root, columns, ascii=ascii)
        if not terminal:
            drawn = drawn[:1]  # it cannot go up a line
        rows = [self._styled(segments) for segments in drawn]
        frame = "\n".join(rows)
        if not above and frame == self._frame and not (force and rows):
            return
        out = [_SYNC_ON] if terminal else []
        if self._height:
            out.append(self._back(terminal))
        if above:
            out.append("".join(row + "\n" for row in above))
        out.append(frame)
        if terminal:
            if rows and not self._hidden:
                out.append(_HIDE)
                self._hidden = True
            elif not rows and self._hidden:
                out.append(_SHOW)
                self._hidden = False
            if self._osc:
                out.append(self._taskbar())
            out.append(_SYNC_OFF)
        stream.write("".join(out))
        stream.flush()
        self._height = len(rows)
        self._frame = frame
        # as JavaScript counts characters: what a notebook's page writes over
        self._covers = len(rows[0].encode("utf-16-le")) // 2 if rows else 0

    def _taskbar(self) -> str:
        first = next(iter(self._live.values()), None)
        if first is None:
            return f"{ESC}]9;4;0;0\a"
        if first.fraction is None:
            return f"{ESC}]9;4;3;0\a"
        return f"{ESC}]9;4;1;{round(100 * first.fraction)}\a"

    def _restore(self) -> None:
        """At exit: give the cursor back, and leave the prompt on a line of its own."""
        with contextlib.suppress(Exception):
            self._give_streams()
        with contextlib.suppress(Exception):
            if self._hidden:
                self.file.write(("\n" if self._height else "") + _SHOW)
                self.file.flush()
                self._hidden = False
