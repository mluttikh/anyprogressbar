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

import contextvars
import itertools
import operator
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


class Bar[T]:
    """Progress through some work. `progress` is this class.

    iterable: what to wrap; its length is the total when it has one.
    desc: what the work is, shown beside the bar.
    total: how many units make it complete; None when that is unknown.
    unit: what is counted ("it", "files", "rows").
    parent: the bar this one is part of; by default the current bar, if any.
    leave: keep the bar once it is done. By default a root stays and a child goes
        (a child that failed or stopped always stays).
    renderer: what shows the tree (a root's only); by default the environment's.
    disable: do nothing at all; iterating then costs nothing.
    min_interval: the least time, in seconds, between two pictures handed to the renderer.
    """

    def __init__(
        self,
        iterable: Iterable[T] | None = None,
        desc: str = "",
        *,
        total: float | None = None,
        unit: str = "it",
        parent: Bar[Any] | None = None,
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
        self._estimator = RateEstimator()
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
                remaining = max(0.0, self.total - self.n) / rate
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
        """End the bar. Without a status: done when the total was reached (or there is none),
        stopped otherwise. Bars still running under it end with it."""
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
        """End the bar as failed."""
        self.close(Status.FAILED, message)

    def __del__(self) -> None:
        try:
            if self.status is Status.RUNNING:
                self.close(Status.STOPPED)
        except Exception:
            pass

    # -- progress --------------------------------------------------------------------------

    def _record(self, dn: float, now: float, *, skip: bool = False) -> None:
        if skip:
            self._estimator.skip(now)
        else:
            self._estimator.update(dn, now)
        if dn:
            self._t_progress = now

    def update(self, n: float = 1, *, skip: bool = False) -> None:
        """`n` more units are done. `skip=True` for units that took no real work (cached,
        already done in an earlier run): they count as done, not towards the rate."""
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
        """Set the position (for work that reports where it is, not how far it moved), the
        total (once it is known, or when it grows), or both."""
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
        """Values to show beside the bar (`loss=0.42, acc=0.91`); they replace the last ones."""
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
            # A loop body that raises does not reach here until the generator is collected:
            # the generator cannot see the body's exception. Use a `with` block when a
            # failure must show at once.
            if self.status is Status.RUNNING:
                with lock:
                    self._record(n - recorded, clock())
                self.close(Status.DONE if exhausted else Status.STOPPED)
            elif _current.get() is self:
                _current.set(self._previous)

    def __repr__(self) -> str:
        total = "?" if self.total is None else fmt.count(self.total)
        return f"<Bar {self.desc!r} {fmt.count(self.n)}/{total} {self.status.value}>"


progress = Bar
