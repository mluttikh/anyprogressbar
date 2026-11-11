"""The bar: how much of some work is done, as a node in a tree, with no idea how it is shown.

Three ways in, one object:

    for x in progress(items, "Loading"): ...          # wrap an iterable

    with progress(total=100, desc="Steps") as bar:    # a block, updated by hand
        bar.update(10)

    bar = progress(total=100); bar.update(); bar.close()

A bar made while another is the current one (inside its loop or its `with` block) becomes its
child. The root of a tree owns the lock and the renderer, and hands the renderer snapshots.
"""

from __future__ import annotations

import contextlib
import contextvars
import itertools
import operator
import sys
import threading
import time
import warnings
from collections.abc import Callable, Iterable, Iterator, Sized
from types import TracebackType
from typing import Any, Self

from anyprogressbar import format as fmt
from anyprogressbar.estimate import RateEstimator
from anyprogressbar.render import NullRenderer, Renderer, default_renderer
from anyprogressbar.state import Snapshot, Status

_current: contextvars.ContextVar[Bar[Any] | None] = contextvars.ContextVar(
    "anyprogressbar_current", default=None
)
_ids = itertools.count(1)

# A bar around a `for` loop cannot see an exception in the loop's body: its generator is just
# closed, as it is after a `break`. So while such a bar runs, the interpreter is asked
# (`sys.monitoring`) to say which exception is on its way up in each thread, and the generator
# looks at that when it is closed. (Decision 0002.)
_flight = threading.local()  # .error: (watch number, the exception that is not yet handled)
_watch_lock = threading.Lock()
_watchers = 0
_watch_number = 0  # which stretch of watching: what an earlier one saw says nothing now
_tool: int | None = None


def _raised(_code: object, _offset: int, error: BaseException) -> None:
    if not isinstance(error, GeneratorExit):  # a generator being closed is not a failure
        _flight.error = (_watch_number, error)


def _handled(_code: object, _offset: int, error: BaseException) -> None:
    pending = getattr(_flight, "error", None)
    if pending is not None and pending[1] is error:
        _flight.error = None


def _watch(on: bool) -> None:
    """Count the loops that are watched; listen for exceptions while there is one."""
    global _watchers, _watch_number, _tool  # noqa: PLW0603
    monitoring = sys.monitoring
    events = monitoring.events
    # where no tool id is free nothing is heard, and a loop that fails ends as stopped
    with _watch_lock, contextlib.suppress(Exception):
        _watchers += 1 if on else -1
        if on and _watchers == 1:
            if _tool is None:
                tool = next(i for i in range(6) if monitoring.get_tool(i) is None)
                monitoring.use_tool_id(tool, "anyprogressbar")
                monitoring.register_callback(tool, events.RAISE, _raised)
                monitoring.register_callback(tool, events.RERAISE, _raised)
                monitoring.register_callback(tool, events.EXCEPTION_HANDLED, _handled)
                _tool = tool
            _watch_number += 1
            monitoring.set_events(_tool, events.RAISE | events.RERAISE | events.EXCEPTION_HANDLED)
        elif not on and _watchers == 0 and _tool is not None:
            monitoring.set_events(_tool, 0)


def _in_flight() -> BaseException | None:
    """The exception that is on its way up in this thread, if any."""
    pending = getattr(_flight, "error", None)
    if pending is not None and pending[0] == _watch_number:
        return pending[1]
    return None


class Bar[T]:
    """Progress through some work. `progress` is this class.

    Wrap an iterable (`for x in progress(items)`), use it as a `with` block and call
    `update`, or call `update` and `close` yourself. A bar made while another one runs
    (inside its loop or its `with` block) becomes that bar's child.

    Args:
        iterable: What to wrap. Its length is the total when it has one.
        desc: What the work is, shown beside the bar.
        total: How many units make the work complete; None when that is unknown.
        unit: What is counted: "it", "files", "rows", "MB".
        parent: The bar this one is part of. By default the bar that is running where this
            one is made, if any.
        weight: How many of its parent's units this bar covers. While it runs, its parent's
            time remaining counts the part of them that is done.
        leave: Keep the bar once it is done. By default a bar of its own stays and a child
            goes; a child that failed or stopped always stays.
        renderer: What shows the bars (used by a bar of its own, not by a child). By default
            the one `set_renderer` set, or the one that suits where the code runs.
        disable: Do nothing at all. Iterating then costs nothing.
        min_interval: The least time, in seconds, between two pictures handed to the
            renderer.
        clock: Where the time comes from, in seconds (for tests).
    """

    def __init__(
        self,
        iterable: Iterable[T] | None = None,
        desc: str = "",
        *,
        total: float | None = None,
        unit: str = "it",
        parent: Bar[Any] | None = None,
        weight: float = 1.0,
        leave: bool | None = None,
        renderer: Renderer | None = None,
        disable: bool = False,
        min_interval: float = 0.1,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.status = Status.PENDING  # first, so that __del__ always finds it
        self.disable = disable
        self._iterable = iterable
        if total is None and iterable is not None:
            if isinstance(iterable, Sized):
                total = len(iterable)
            else:
                total = operator.length_hint(iterable) or None
        self.id = next(_ids)
        self.desc = desc
        self.n: float = 0
        self.total = total
        self.unit = unit
        self.message = ""
        self.metrics: dict[str, str] = {}
        self.children: list[Bar[Any]] = []
        self.weight = weight
        self._estimator = RateEstimator()
        self._credited = 0.0  # the furthest `_reached()` the estimator was told of
        self._t_start = self._t_end = self._t_progress = 0.0
        self._previous: Bar[Any] | None = None

        if parent is None and not disable:
            current = _current.get()
            if current is not None and current.status is Status.RUNNING:
                parent = current
        self.parent = parent
        self.leave = leave if leave is not None else parent is None
        self._root: Bar[Any] = parent._root if parent is not None else self
        if parent is None:
            self._lock = threading.RLock()
            self._clock = clock
            self._renderer = renderer
            self._min_interval = min_interval
            self._last_emit = float("-inf")
        elif not disable:
            with self._root._lock:
                parent.children.append(self)

    # -- showing ---------------------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        """The bar and its children as they are now."""
        root = self._root
        with root._lock:
            return self._snapshot(root._clock())

    def _snapshot(self, now: float) -> Snapshot:
        started = self.status is not Status.PENDING
        end = self._t_end if self.status.finished else now
        rate = remaining = None
        if self.status is Status.RUNNING:
            rate = self._estimator.rate(now)
            if rate is not None and self.total is not None:
                remaining = max(0.0, self.total - self._reached()) / rate
        return Snapshot(
            id=self.id,
            desc=self.desc,
            n=self.n,
            total=self.total,
            unit=self.unit,
            status=self.status,
            elapsed=end - self._t_start if started else 0.0,
            rate=rate,
            remaining=remaining,
            since_progress=end - self._t_progress if started else 0.0,
            message=self.message,
            leave=self.leave,
            metrics=dict(self.metrics),
            children=tuple(c._snapshot(now) for c in self.children),
        )

    def _render(self, method: str, now: float) -> None:
        """Hand the root's picture to the renderer. A renderer that breaks is dropped: showing
        progress must never stop the work."""
        root = self._root
        root._last_emit = now
        try:
            getattr(root._renderer, method)(root._snapshot(now))
        except Exception as error:
            root._renderer = NullRenderer()
            warnings.warn(f"progress display stopped: {error!r}", RuntimeWarning, stacklevel=4)

    def _emit(self, now: float, *, force: bool = False) -> None:
        root = self._root
        if root.status is Status.PENDING:
            return
        if force or now - root._last_emit >= root._min_interval:
            self._render("update", now)

    def refresh(self) -> None:
        """Show the bar as it is now, whatever the time since the last picture."""
        if self.disable:
            return
        root = self._root
        with root._lock:
            self._emit(root._clock(), force=True)

    # -- life ------------------------------------------------------------------------------

    def start(self) -> Self:
        """Start the clock. Updating, iterating and entering a `with` block do this."""
        if self.disable or self.status is not Status.PENDING:
            return self
        root = self._root
        with root._lock:
            if self.parent is not None:
                self.parent.start()
            else:
                if root._renderer is None:
                    root._renderer = default_renderer()
                attach = getattr(root._renderer, "attach", None)
                if attach is not None:  # a renderer that draws on a timer asks for pictures
                    attach(self.id, self.snapshot)
            now = root._clock()
            self._t_start = self._t_progress = now
            self._estimator.start(now)
            self.status = Status.RUNNING
            self._emit(now, force=True)
        return self

    def close(self, status: Status | None = None, message: str = "") -> None:
        """End the bar. Bars still running under it end with it.

        Args:
            status: How it ended. By default done when the total was reached (or there is
                none), stopped otherwise.
            message: Why it failed or stopped, shown beside it.
        """
        if self.disable or self.status.finished:
            return
        if _current.get() is self:
            _current.set(self._previous)
        root = self._root
        with root._lock:
            if status is None:
                complete = self.total is None or self.n >= self.total
                status = Status.DONE if complete else Status.STOPPED
            if self.status is Status.PENDING:  # never shown: nothing to tell
                self.status = status
                if self.parent is not None and self in self.parent.children:
                    self.parent.children.remove(self)
                return
            for child in list(self.children):
                child.close(Status.STOPPED if status is Status.DONE else status)
            now = root._clock()
            self.status = status
            self.message = message
            self._t_end = now
            if self.parent is None:
                self._render("close", now)
                return
            if status is Status.DONE and not self.leave:
                self.parent.children.remove(self)
            self._emit(now, force=True)

    def fail(self, message: str = "") -> None:
        """End the bar as failed.

        Args:
            message: Why, shown beside the bar.
        """
        self.close(Status.FAILED, message)

    def __del__(self) -> None:
        try:
            if self.status is Status.RUNNING:
                self.close(Status.STOPPED)
        except Exception:
            pass

    # -- progress --------------------------------------------------------------------------

    def _reached(self) -> float:
        """How far the bar is, counting the done part of the children that are running."""
        reached = self.n
        for child in self.children:
            if child.status is Status.RUNNING and child.total:
                part = min(1.0, max(0.0, child._reached() / child.total))
                reached += child.weight * part
        return reached

    def _record(self, dn: float, now: float, *, skip: bool = False) -> None:
        """Tell the estimators, this bar's and those above it, how far the work is. They
        only hear of ground that is new: a child that ends takes its part away, and its
        parent's own update then puts it back."""
        if dn:
            self._t_progress = now
        bar: Bar[Any] | None = self
        while bar is not None and bar.status is Status.RUNNING:
            reached = bar._reached()
            gained = max(0.0, reached - bar._credited)
            bar._credited = max(bar._credited, reached)
            if skip:
                bar._estimator.skip(now)
            else:
                bar._estimator.update(gained, now)
            bar = bar.parent

    def update(self, n: float = 1, *, skip: bool = False) -> None:
        """Count units as done.

        Args:
            n: How many more units are done.
            skip: The units took no real work (cached, or done in an earlier run): they
                count as done, but not towards the rate and the time remaining.
        """
        if self.disable:
            return
        if self.status is Status.PENDING:
            self.start()
        if self.status is not Status.RUNNING:
            return
        root = self._root
        with root._lock:
            now = root._clock()
            self.n += n
            self._record(n, now, skip=skip)
            self._emit(now)

    def set(self, n: float | None = None, *, total: float | None = None) -> None:
        """Set where the work is, or how much there is.

        Args:
            n: The position, for work that reports where it is rather than how far it
                moved.
            total: The total, once it is known or when it changes.
        """
        if self.disable:
            return
        if total is not None:
            self.total = total
        if n is not None:
            self.update(n - self.n)
        else:
            self._changed()

    def _changed(self) -> None:
        root = self._root
        with root._lock:
            self._emit(root._clock())

    def set_description(self, desc: str) -> None:
        """Change what the work is called."""
        if self.disable:
            return
        self.desc = desc
        self._changed()

    def set_postfix(self, **metrics: Any) -> None:
        """Show values beside the bar (`loss=0.42, acc=0.91`). They replace the last ones;
        floats are shown with three significant digits."""
        if self.disable:
            return
        self.metrics = {key: fmt.metric(value) for key, value in metrics.items()}
        self._changed()

    # -- as a block ------------------------------------------------------------------------

    def _make_current(self) -> None:
        self._previous = _current.get()
        _current.set(self)

    def __enter__(self) -> Self:
        if not self.disable:
            self.start()
            self._make_current()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.close()
        elif issubclass(exc_type, KeyboardInterrupt | GeneratorExit):
            self.close(Status.STOPPED, "interrupted" if exc_type is KeyboardInterrupt else "")
        else:
            self.close(
                Status.FAILED, f"{exc_type.__name__}: {exc}" if str(exc) else exc_type.__name__
            )

    # -- as an iterable --------------------------------------------------------------------

    def __iter__(self) -> Iterator[T]:
        if self._iterable is None:
            raise TypeError("this bar wraps no iterable; call update() as the work proceeds")
        if self.disable:
            return iter(self._iterable)
        return self._iterate(self._iterable)

    def _iterate(self, iterable: Iterable[T]) -> Iterator[T]:
        """Yield the items, counting them. Each item costs an add, a store and a comparison;
        the clock is read every `gate` items, where `gate` is kept at about half a
        `min_interval`'s worth of items."""
        self.start()
        self._make_current()
        _watch(True)
        root = self._root
        clock, lock = root._clock, root._lock
        target = root._min_interval / 2
        n = recorded = self.n
        gate = 1
        check_at = n + gate
        last = clock()
        exhausted = False
        try:
            for item in iterable:
                yield item
                n += 1
                self.n = n
                if n >= check_at:
                    now = clock()
                    with lock:
                        if self.status is Status.RUNNING:
                            self._record(n - recorded, now)
                            self._emit(now)
                    recorded = n
                    dt = now - last
                    last = now
                    grown = gate * 10
                    gate = max(1, min(int(gate * target / dt), grown)) if dt > 0 else grown
                    check_at = n + gate
            exhausted = True
        finally:
            # After a `break`, or an exception in the loop's body, the generator is closed
            # and arrives here; which of the two it was, the interpreter has told `_flight`.
            error = None if exhausted else _in_flight()
            _watch(False)
            if self.status is Status.RUNNING:
                with lock:
                    self._record(n - recorded, clock())
                if exhausted:
                    self.close(Status.DONE)
                elif error is None:
                    self.close(Status.STOPPED)
                elif isinstance(error, KeyboardInterrupt):
                    self.close(Status.STOPPED, "interrupted")
                else:
                    reason = type(error).__name__ + (f": {error}" if str(error) else "")
                    self.close(Status.FAILED, reason)
            elif _current.get() is self:
                _current.set(self._previous)
            if _watchers == 0:
                _flight.error = None  # do not keep the exception, and its frames, alive

    def __repr__(self) -> str:
        total = "?" if self.total is None else fmt.count(self.total)
        return f"<Bar {self.desc!r} {fmt.count(self.n)}/{total} {self.status.value}>"


progress = Bar
