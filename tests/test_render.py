from __future__ import annotations

import io

import pytest

from anyprogressbar import LogRenderer, NullRenderer, progress, set_renderer
from anyprogressbar import format as fmt
from anyprogressbar.render import default_renderer


def lines(out: io.StringIO) -> list[str]:
    return out.getvalue().splitlines()


def test_log_lines_while_running_and_one_at_the_end(clock):
    out = io.StringIO()
    log = LogRenderer(out, interval=5.0, delay=2.0)
    for _ in progress(range(100), "Loading", unit="files", renderer=log, clock=clock):
        clock.tick(0.2)  # 20 seconds in all
    assert lines(out) == [
        "Loading: 10/100 (10%), 00:02 elapsed, about 18 s left",
        "Loading: 35/100 (35%), 00:07 elapsed, about 13 s left",
        "Loading: 60/100 (60%), 00:12 elapsed, about 8 s left",
        "Loading: 85/100 (85%), 00:17 elapsed, about 3 s left",
        "Loading: done, 100 files in 00:20 (5 files/s)",
    ]


def test_work_that_is_done_quickly_prints_nothing(clock):
    out = io.StringIO()
    for _ in progress(range(10), renderer=LogRenderer(out), clock=clock):
        clock.tick(0.1)
    assert out.getvalue() == ""


def test_a_quick_failure_is_still_reported(clock):
    out = io.StringIO()
    with (
        pytest.raises(RuntimeError),
        progress(total=10, desc="Import", renderer=LogRenderer(out), clock=clock) as bar,
    ):
        bar.update(4)
        clock.tick(0.5)
        raise RuntimeError("boom")
    assert lines(out) == ["Import: failed at 4/10 (40%) after 00:00: RuntimeError: boom"]


def test_without_a_total_the_line_gives_the_count_and_the_rate(clock):
    out = io.StringIO()
    with progress(desc="Scanning", unit="rows", renderer=LogRenderer(out), clock=clock) as bar:
        for _ in range(30):
            clock.tick(0.1)
            bar.update(50)
    assert lines(out) == [
        "Scanning: 1000 rows, 00:02 elapsed, 500 rows/s",
        "Scanning: done, 1500 rows in 00:03 (500 rows/s)",
    ]


def test_the_line_names_the_running_child_and_the_metrics(clock):
    out = io.StringIO()
    log = LogRenderer(out, interval=100.0, delay=1.0)
    for epoch in (outer := progress(range(2), "Epochs", renderer=log, clock=clock)):
        outer.set_postfix(loss=0.5)
        for _ in progress(range(4), f"Batches {epoch}"):
            clock.tick(0.5)
    assert lines(out)[0] == "Epochs: 0/2 (0%), 00:01 elapsed, loss=0.5 | Batches 0: 2/4 (50%)"
    assert lines(out)[-1] == "Epochs: done, 2 it in 00:04 (30 it/min)"


def test_times_and_rates_as_text():
    assert [fmt.elapsed(s) for s in (0, 42.9, 725, 3723)] == ["00:00", "00:42", "12:05", "1:02:03"]
    assert [fmt.remaining(s) for s in (0.2, 8.4, 42, 58, 200, 3500)] == [
        "1 s", "8 s", "40 s", "1 min", "3 min", "58 min",
    ]  # fmt: skip
    assert [fmt.remaining(s) for s in (3600, 8000, 90000)] == ["1 h", "2 h 15 min", "25 h"]
    assert fmt.rate(227.3, "it") == "227 it/s"
    assert fmt.rate(2.5, "it") == "2.5 it/s"
    assert fmt.rate(0.04, "it") == "2.4 it/min"
    assert fmt.rate(0.0004, "files") == "1.44 files/h"
    assert [fmt.count(v) for v in (3, 3.0, 2.5, 1200)] == ["3", "3", "2.5", "1200"]


def test_the_default_renderer_follows_set_renderer_then_the_environment(monkeypatch):
    set_renderer(None)
    monkeypatch.delenv("ANYPROGRESSBAR", raising=False)
    assert isinstance(default_renderer(), LogRenderer)
    monkeypatch.setenv("ANYPROGRESSBAR", "off")
    assert isinstance(default_renderer(), NullRenderer)
    monkeypatch.setenv("ANYPROGRESSBAR", "sparkles")
    with pytest.warns(UserWarning, match="not a renderer"):
        assert isinstance(default_renderer(), LogRenderer)
    mine = LogRenderer(io.StringIO())
    set_renderer(mine)
    assert default_renderer() is mine
    with pytest.raises(ValueError, match="unknown renderer"):
        set_renderer("sparkles")
