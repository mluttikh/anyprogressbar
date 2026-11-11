from __future__ import annotations

import io
import os
import re
import time
from typing import Any

import pytest
from screen import Screen

from anyprogressbar import progress, render, set_renderer, write
from anyprogressbar.terminal import TerminalRenderer, cells, clip, fill


def terminal(screen, **given) -> TerminalRenderer:
    options: dict[str, Any] = {
        "columns": 81,
        "color": False,
        "threaded": False,
        "delay": 0.0,
    } | given
    return TerminalRenderer(screen, **options)


def parts(row: str) -> tuple[str, str, str]:
    """A drawn line as its name and percentage, its bar, and its numbers."""
    match = re.fullmatch(r"(.*?) [▕\[](.*)[▏\]] (.*)", row)
    assert match, row
    return match.group(1), match.group(2), match.group(3)


def test_a_bar_is_redrawn_on_one_line_and_its_last_state_stays(clock):
    screen = Screen()
    bar = progress(range(40), "Loading", renderer=terminal(screen), clock=clock)
    for i in bar:
        clock.tick(0.5)
        if i == 9:
            bar.refresh()
            assert screen.display() == [
                "Loading  22% ▕████▌               ▏ 9/40 · 00:05 · about 16 s left · 2 it/s"
            ]
            assert screen.cursor_hidden
    assert screen.display() == [
        "Loading 100% ▕████████████████████▏ 40/40 · done in 00:20 · 2 it/s"
    ]
    assert not screen.cursor_hidden
    screen.write("$ next command")  # the prompt comes back on a line of its own
    assert screen.display()[1] == "$ next command"


def test_children_are_lines_under_their_parent_and_go_when_done(clock):
    screen = Screen()
    for epoch in progress(range(2), "Epochs", renderer=terminal(screen), clock=clock):
        for i in (inner := progress(range(4), f"Batches {epoch}")):
            clock.tick(1.0)
            if (epoch, i) == (1, 1):
                inner.refresh()
                assert screen.display() == [
                    "Epochs       50% ▕██████████          ▏ 1/2 · 00:06",
                    "  Batches 1  25% ▕█████               ▏ 1/4 · 00:02",
                ]
    assert screen.display() == [
        "Epochs 100% ▕████████████████████▏ 2/2 · done in 00:08 · 15 it/min"
    ]


def test_the_bar_keeps_its_width_as_the_numbers_beside_it_change(clock):
    screen = Screen()
    widths = set()
    with progress(total=5000, desc="Load", renderer=terminal(screen), clock=clock) as bar:
        for _ in range(50):
            clock.tick(0.7)
            bar.update(100)
            bar.set_postfix(loss=1 / (1 + bar.n))
            widths.add(cells(parts(screen.display()[0])[1]))
    assert widths == {20}


def test_a_failure_stays_on_screen_with_its_reason(clock):
    screen = Screen()
    with (
        pytest.raises(KeyError),
        progress(total=10, desc="Import", renderer=terminal(screen), clock=clock) as bar,
    ):
        clock.tick(2)
        bar.update(4)
        raise KeyError
    name, drawn, numbers = parts(screen.display()[0])
    assert (name, drawn.count("█")) == ("Import  40%", 8)
    assert numbers == "4/10 · failed after 00:02: KeyError"


def test_a_long_reason_takes_the_bars_place(clock):
    screen = Screen()
    reason = "the file has a row that cannot be read"
    with progress(total=10, desc="Import", renderer=terminal(screen), clock=clock) as bar:
        bar.update(4)
        bar.fail(reason)
    assert screen.display() == [f"Import  40% 4/10 · failed after 00:00: {reason}"]


def test_work_done_within_the_delay_is_never_drawn(clock):
    screen = Screen()
    for _ in progress(range(10), renderer=terminal(screen, delay=0.5), clock=clock):
        clock.tick(0.01)
    assert screen.raw.replace("\x1b[?2026h", "").replace("\x1b[?2026l", "") == ""


def test_a_bar_that_is_not_left_is_erased_unless_it_failed(clock):
    screen = Screen()
    renderer = terminal(screen)
    with progress(total=2, desc="gone", leave=False, renderer=renderer, clock=clock) as bar:
        bar.update(2)
    assert screen.display() == []
    with (
        pytest.raises(RuntimeError),
        progress(total=2, desc="kept", leave=False, renderer=renderer, clock=clock),
    ):
        raise RuntimeError
    assert parts(screen.display()[0])[2] == "0/2 · failed after 00:00: RuntimeError"


def test_without_a_total_a_block_runs_back_and_forth(clock):
    screen = Screen()
    seen = set()
    with progress(desc="Scanning", unit="rows", renderer=terminal(screen), clock=clock) as bar:
        for _ in range(8):
            clock.tick(0.25)
            bar.update(100)
            name, drawn, numbers = parts(screen.display()[0])
            assert (name, drawn.count("█"), cells(drawn)) == ("Scanning", 3, 20)
            seen.add(drawn.index("█"))
        assert numbers == "800 rows · 00:02 · 400 rows/s"
    assert len(seen) > 4  # it moves
    assert screen.display() == [
        "Scanning ▕████████████████████▏ 800 rows · done in 00:02 · 400 rows/s"
    ]


def test_a_stall_is_said_instead_of_a_time_remaining(clock):
    screen = Screen()
    with progress(total=100, desc="Sync", renderer=terminal(screen), clock=clock) as bar:
        for _ in range(10):
            clock.tick(1)
            bar.update()
        assert parts(screen.display()[0])[2] == "10/100 · 00:10 · about 2 min left · 1 it/s"
        clock.tick(45)
        bar.refresh()
        assert parts(screen.display()[0])[2] == "10/100 · 00:55 · no progress for 45 s"
        bar.set(100)


def test_slow_work_is_not_called_stalled(clock):
    screen = Screen()
    with progress(total=10, desc="Slow", renderer=terminal(screen), clock=clock) as bar:
        for _ in range(4):
            clock.tick(60)
            bar.update()
        clock.tick(200)  # a unit takes a minute: 200 s without one is not yet a stall
        bar.refresh()
        assert "no progress" not in screen.display()[0]
        clock.tick(200)
        bar.refresh()
        assert "no progress for 7 min" in screen.display()[0]
        bar.set(10)


def test_write_prints_above_the_bars(clock):
    screen = Screen()
    set_renderer(terminal(screen))
    with progress(total=4, desc="Work", clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        write("saved", 1, file=screen)
        clock.tick(0.2)
        bar.update()
        write("saved", 2, file=screen)
        assert screen.display() == [
            "saved 1",
            "saved 2",
            "Work  50% ▕██████████          ▏ 2/4 · 00:00",
        ]
        bar.update(2)


def test_write_to_another_stream_leaves_the_bars_whole(clock):
    screen, out = Screen(), io.StringIO()
    set_renderer(terminal(screen))
    with progress(total=4, desc="Work", clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        write("result", file=out)
        assert out.getvalue() == "result\n"
        assert screen.display() == ["Work  25% ▕█████               ▏ 1/4 · 00:00"]
        bar.update(3)


def test_write_without_live_bars_is_print():
    out = io.StringIO()
    set_renderer("log")
    write("a", "b", sep="-", file=out)
    assert out.getvalue() == "a-b\n"


def test_no_line_is_wider_than_the_terminal(clock):
    for columns in (20, 40, 60):
        screen = Screen()
        renderer = terminal(screen, columns=columns)
        with progress(
            total=1000, desc="A rather long description of the work", renderer=renderer, clock=clock
        ) as bar:
            with progress(total=50, desc="a child with 日本語 in its name") as child:
                clock.tick(0.2)
                child.update(7)
                bar.update(123)
                bar.set_postfix(loss=0.123, accuracy=0.987)
                bar.refresh()
                assert len(screen.display()) == 2
                assert all(cells(row) < columns for row in screen.display())
            bar.set(1000)
        assert all(cells(row) < columns for row in screen.display())


def test_ascii_for_streams_that_cannot_show_blocks(clock):
    class Latin(Screen):
        encoding = "latin-1"

    screen = Latin()
    with progress(total=4, desc="Copy", renderer=terminal(screen), clock=clock) as bar:
        clock.tick(0.2)
        bar.update(1)
        assert screen.display() == ["Copy  25% [#####---------------] 1/4, 00:00"]
        bar.update(3)
    assert screen.raw.isascii()


def test_colour_by_status_and_none_when_switched_off(clock):
    coloured, plain = Screen(), Screen()
    for screen, color in ((coloured, True), (plain, False)):
        with progress(total=1, renderer=terminal(screen, color=color), clock=clock) as bar:
            bar.update()
    assert "\x1b[36m" in coloured.raw  # running: cyan
    assert "\x1b[32m" in coloured.raw  # done: green
    assert "\x1b[3" not in plain.raw
    assert coloured.display() == plain.display()


def test_the_thread_keeps_the_clock_ticking_through_a_slow_item():
    screen = Screen()
    renderer = TerminalRenderer(screen, columns=81, color=False, interval=0.02, delay=0.0)
    with progress(total=2, desc="Slow", renderer=renderer) as bar:
        bar.update()
        time.sleep(1.15)  # one slow item: the loop tells the renderer nothing meanwhile
        assert parts(screen.display()[0])[2] == "1/2 · 00:01"
        bar.update()
    assert parts(screen.display()[0])[2].startswith("2/2 · done in 00:01")
    time.sleep(0.1)
    assert renderer._thread is None  # it ends when nothing is live
    assert not screen.cursor_hidden


def test_two_trees_at_once_share_the_screen(clock):
    screen = Screen()
    renderer = terminal(screen)
    a = progress(total=2, desc="first", renderer=renderer, clock=clock).start()
    b = progress(total=2, desc="second", renderer=renderer, clock=clock).start()
    assert [row.split()[0] for row in screen.display()] == ["first", "second"]
    a.update(2)
    a.close()
    clock.tick(0.2)
    b.update(1)
    assert [row.split()[0] for row in screen.display()] == ["first", "second"]
    assert "done" in screen.display()[0]
    b.update(1)
    b.close()
    assert all("done" in row for row in screen.display())


def test_taskbar_progress_only_where_the_terminal_is_known_to_take_it(clock, monkeypatch):
    for name in ("WT_SESSION", "ConEmuANSI", "TERM_PROGRAM"):
        monkeypatch.delenv(name, raising=False)
    quiet = Screen()
    with progress(total=4, renderer=terminal(quiet), clock=clock) as bar:
        bar.update(4)
    assert quiet.osc == []
    monkeypatch.setenv("WT_SESSION", "1")
    screen = Screen()
    with progress(total=4, renderer=terminal(screen), clock=clock) as bar:
        clock.tick(0.2)
        bar.update(1)
        bar.update(3)
    assert screen.osc[0] == "9;4;1;0"
    assert "9;4;1;25" in screen.osc
    assert screen.osc[-1] == "9;4;0;0"  # cleared at the end


def test_cells_clip_and_fill():
    assert (cells("abc"), cells("日本"), cells("é")) == (3, 4, 1)
    assert clip("abcdef", 4) == "abc…"
    assert clip("日本語", 5) == "日本…"
    assert clip("abc", 3) == "abc"
    assert fill(0.5, 4, ascii=False) == ("██", "  ")
    assert fill(1 / 32, 4, ascii=False) == ("▏", "   ")
    assert fill(1.0, 4, ascii=False) == ("████", "")
    assert fill(0.5, 4, ascii=True) == ("##", "--")


def test_detection(monkeypatch):
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    for name in ("CI", "TERM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(render.sys, "platform", "linux")
    monkeypatch.setattr(render.sys, "stderr", io.StringIO())
    assert render.detect() == "log"  # a pipe or a file
    monkeypatch.setattr(render.sys, "stderr", Tty())
    assert render.detect() == "terminal"
    monkeypatch.setenv("TERM", "dumb")
    assert render.detect() == "log"
    monkeypatch.delenv("TERM")
    monkeypatch.setenv("CI", "true")
    assert render.detect() == "log"
    monkeypatch.setattr(render.sys, "stderr", None)
    assert render.detect() == "log"


def test_a_terminal_that_reports_no_width_is_taken_as_80_columns(clock, monkeypatch):
    monkeypatch.setattr("os.get_terminal_size", lambda fd: os.terminal_size((0, 0)))

    class Sized(Screen):
        def fileno(self) -> int:
            return 2

    screen = Sized()
    renderer = TerminalRenderer(screen, color=False, threaded=False, delay=0.0)
    with progress(total=4, desc="Work", renderer=renderer, clock=clock) as bar:
        clock.tick(0.2)
        bar.update(2)
        assert screen.display() == ["Work  50% ▕█████████▌         ▏ 2/4 · 00:00"]
        bar.update(2)
