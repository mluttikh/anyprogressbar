from __future__ import annotations

import pytest

from anyprogressbar import Snapshot, set_renderer


class Clock:
    """A clock that moves only when told to."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def tick(self, seconds: float) -> None:
        self.t += seconds


class Recorder:
    """A renderer that keeps every picture it is given."""

    def __init__(self) -> None:
        self.updates: list[Snapshot] = []
        self.closed: list[Snapshot] = []

    def update(self, root: Snapshot) -> None:
        self.updates.append(root)

    def close(self, root: Snapshot) -> None:
        self.closed.append(root)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture(autouse=True)
def quiet():
    """Bars made without a renderer show nothing during the tests."""
    set_renderer("off")
    yield
    set_renderer(None)
