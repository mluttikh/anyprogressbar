"""What a renderer is given: a bar's status, and a picture of a tree of bars at one moment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """Where a bar is in its life."""

    PENDING = "pending"  # made, not started
    RUNNING = "running"
    DONE = "done"  # the work finished
    FAILED = "failed"  # an exception, or fail() was called
    STOPPED = "stopped"  # ended before the work finished: a break, Ctrl-C, or left incomplete

    @property
    def finished(self) -> bool:
        """Done, failed or stopped."""
        return self in (Status.DONE, Status.FAILED, Status.STOPPED)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A bar and its children at one moment: what a renderer is given. Immutable, and plain
    data throughout.

    Attributes:
        id: The bar's number, the same in every snapshot of it.
        desc: What the work is.
        n: How many units are done.
        total: How many units make the work complete; None when unknown.
        unit: What is counted.
        status: Where the bar is in its life.
        elapsed: Seconds since the bar started (to its end, once it has ended).
        rate: Units per second; None until the estimate is stable.
        remaining: Seconds left; None without a total or a rate.
        since_progress: Seconds since `n` last changed.
        message: Why the bar failed or stopped.
        leave: Keep the bar on screen once it is done.
        metrics: The values set with `Bar.set_postfix`, as text.
        children: The bars inside this one, in the order they were made.
    """

    id: int
    desc: str
    n: float
    total: float | None
    unit: str
    status: Status
    elapsed: float
    rate: float | None
    remaining: float | None
    since_progress: float
    message: str = ""
    leave: bool = True
    metrics: dict[str, str] = field(default_factory=dict)
    children: tuple[Snapshot, ...] = ()

    @property
    def fraction(self) -> float | None:
        """Progress from 0 to 1, or None without a total."""
        if self.total is None:
            return None
        if self.total <= 0:
            return 1.0
        return min(1.0, max(0.0, self.n / self.total))

    def as_dict(self) -> dict[str, Any]:
        """The tree as JSON-ready data: what the widget is sent (js/src/format.ts reads it)."""
        return {
            "id": self.id,
            "desc": self.desc,
            "n": self.n,
            "total": self.total,
            "unit": self.unit,
            "status": self.status.value,
            "elapsed": self.elapsed,
            "rate": self.rate,
            "remaining": self.remaining,
            "since_progress": self.since_progress,
            "message": self.message,
            "leave": self.leave,
            "metrics": dict(self.metrics),
            "children": [child.as_dict() for child in self.children],
        }
