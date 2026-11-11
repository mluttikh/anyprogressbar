"""What a renderer is given: a bar's status, and a picture of a tree of bars at one moment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Status(StrEnum):
    """Where a bar is in its life."""

    PENDING = "pending"  # made, not started
    RUNNING = "running"
    DONE = "done"  # the work finished
    FAILED = "failed"  # an exception, or fail() was called
    STOPPED = "stopped"  # ended before the work finished: a break, Ctrl-C, or left incomplete

    @property
    def finished(self) -> bool:
        return self in (Status.DONE, Status.FAILED, Status.STOPPED)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A bar and its children at one moment. Immutable, and plain data throughout."""

    id: int
    desc: str
    n: float
    total: float | None
    unit: str
    status: Status
    elapsed: float  # seconds since the bar started (to its end, once finished)
    rate: float | None  # units per second; None until the estimate is stable
    remaining: float | None  # seconds; None without a total or a rate
    since_progress: float  # seconds since n last changed
    message: str = ""  # why it failed or stopped
    leave: bool = True  # keep the bar on screen once it is done
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
