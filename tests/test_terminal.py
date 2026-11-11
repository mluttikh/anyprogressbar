from __future__ import annotations

import io
import logging
import os
import re
import sys
import threading
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
                    # the parent's time remaining counts the quarter of its second unit
                    (
                        "Epochs       50% ▕██████████          ▏ 1/2 · 00:06"
                        " · about 3 s left · 15 it/min"
                    ),
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


def test_a_bar_whose_child_moves_is_not_stalled(clock):
    screen = Screen()
    with progress(total=3, desc="Epochs", renderer=terminal(screen), clock=clock) as outer:
        outer.update()
        with progress(total=500, desc="Batches") as inner:
            for _ in range(100):
                clock.tick(0.5)
                inner.update()
            assert "no progress" not in "".join(screen.display())
            clock.tick(60)
            inner.refresh()
            assert all("no progress for 1 min" in row for row in screen.display())
            inner.set(500)
        outer.set(3)


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


def terminal_streams(monkeypatch) -> Screen:
    """A terminal that standard output, standard error and the bars all write to. (Made in
    the test itself: pytest sets its own streams again after the fixtures.)"""
    screen = Screen()
    monkeypatch.setattr(sys, "stdout", screen)
    monkeypatch.setattr(sys, "stderr", screen)
    return screen


def test_print_and_logging_go_above_the_bars_and_the_streams_come_back(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    log = logging.getLogger("anyprogressbar.test.print")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(handler)
    try:
        set_renderer(terminal(tty))
        with progress(total=4, desc="Work", clock=clock) as bar:
            assert sys.stdout is not tty
            assert handler.stream is not tty
            clock.tick(0.2)
            bar.update()
            print("saved", 1)
            log.warning("disk almost full")
            clock.tick(0.2)
            bar.update()
            print("two\nlines")
            assert tty.display() == [
                "saved 1",
                "WARNING disk almost full",
                "two",
                "lines",
                "Work  50% ▕██████████          ▏ 2/4 · 00:00",
            ]
            bar.update(2)
        assert sys.stdout is tty
        assert sys.stderr is tty
        assert handler.stream is tty
        print("after")
        assert tty.display()[-2:] == [
            "Work 100% ▕████████████████████▏ 4/4 · done in 00:00 · 10 it/s",
            "after",
        ]
    finally:
        log.removeHandler(handler)


def test_a_line_printed_in_parts_is_one_line(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty))
    with progress(total=2, desc="Work", clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        print("a", end="")
        print("b", end="")
        bar.refresh()
        print("c")
        assert tty.display() == ["abc", "Work  50% ▕██████████          ▏ 1/2 · 00:00"]
        bar.update()


def test_a_prompt_takes_the_screen_until_its_line_is_finished(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty))
    with progress(total=2, desc="Work", clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        print("Name: ", end="", flush=True)  # as input() does
        assert tty.display() == ["Name:"]
        bar.refresh()  # the bars do not draw while the prompt waits
        assert tty.display() == ["Name:"]
        tty.write("Mark\n")  # what the terminal echoes as it is typed
        print("Hello, Mark")
        assert tty.display() == [
            "Name: Mark",
            "Hello, Mark",
            "Work  50% ▕██████████          ▏ 1/2 · 00:00",
        ]
        bar.update()


def test_a_prompt_that_is_never_finished_is_left_on_its_own_line(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty))
    with progress(total=2, desc="Work", clock=clock) as bar:
        clock.tick(0.2)
        bar.update()
        print("Continue? ", end="", flush=True)
        bar.update()
    assert tty.display() == [
        "Continue?",
        "Work 100% ▕████████████████████▏ 2/2 · done in 00:00 · 10 it/s",
    ]


def test_output_to_a_file_or_pipe_is_left_alone(clock, monkeypatch):
    screen, out = Screen(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", screen)
    set_renderer(terminal(screen))
    with progress(total=2, desc="Work", clock=clock) as bar:
        assert sys.stdout is out  # `script > file`: printing cannot spoil the bars
        assert sys.stderr is not screen
        clock.tick(0.2)
        bar.update()
        print("result")
        bar.update()
    assert out.getvalue() == "result\n"
    assert sys.stderr is screen


def test_a_stream_replaced_by_someone_else_meanwhile_is_left_as_it_is(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty))
    other = io.StringIO()
    with progress(total=2, desc="Work", clock=clock) as bar:
        held = sys.stdout
        monkeypatch.setattr(sys, "stdout", other)
        bar.update(2)
    assert sys.stdout is other
    held.write("still works\n")  # a stream kept from before passes straight through now
    assert tty.display()[-1] == "still works"


def test_no_redirection_when_asked_for_none(clock, monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty, redirect=False))
    with progress(total=2, desc="Work", clock=clock) as bar:
        assert sys.stdout is tty
        bar.update(2)


def test_printing_from_threads_keeps_lines_whole(monkeypatch):
    tty = terminal_streams(monkeypatch)
    set_renderer(terminal(tty, threaded=True, interval=0.01, delay=0.0))

    def chatter(name: str) -> None:
        for i in range(50):
            print(f"{name} line {i}")

    with progress(total=4, desc="Work") as bar:
        threads = [threading.Thread(target=chatter, args=(f"t{k}",)) for k in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
            bar.update()
    shown = tty.display()
    printed = [line for line in shown if " line " in line]
    assert sorted(printed) == sorted(f"t{k} line {i}" for k in range(4) for i in range(50))
    assert shown[-1].startswith("Work 100%")


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


SCRIPT = """
import logging, threading, time, warnings
from anyprogressbar import progress

logging.basicConfig(format="%(levelname)s %(message)s")  # holds the real stderr
log = logging.getLogger("job")

def chatter():
    for i in range(3):
        print(f"from a thread {i}")

with progress(total=12, desc="Work") as bar:
    for i in range(12):
        time.sleep(0.1)
        bar.update()
        if i == 6:
            print("printed")
            log.warning("logged")
            warnings.warn("warned", stacklevel=1)
            worker = threading.Thread(target=chatter)
            worker.start()
            worker.join()
print("after")
"""


@pytest.mark.skipif(sys.platform == "win32", reason="no pseudo-terminals on Windows")
def test_in_a_real_terminal_nothing_printed_breaks_the_bars(tmp_path):
    import fcntl
    import pty
    import struct
    import subprocess
    import termios

    script = tmp_path / "job.py"
    script.write_text(SCRIPT, encoding="utf-8")
    leader, follower = pty.openpty()
    fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
    env = {k: v for k, v in os.environ.items() if k not in ("CI", "ANYPROGRESSBAR", "NO_COLOR")}
    env |= {"TERM": "xterm-256color", "NO_COLOR": "1"}
    child = subprocess.Popen(
        [sys.executable, str(script)], stdin=follower, stdout=follower, stderr=follower, env=env
    )
    os.close(follower)
    raw = b""
    while True:
        try:
            chunk = os.read(leader, 4096)
        except OSError:  # the other end is closed (Linux)
            break
        if not chunk:  # (macOS)
            break
        raw += chunk
    os.close(leader)
    assert child.wait(timeout=30) == 0
    screen = Screen()
    screen.write(raw.decode("utf-8"))
    shown = screen.display()
    assert shown[0] == "printed"
    assert shown[1] == "WARNING logged"
    assert shown[2].endswith("UserWarning: warned")
    assert shown[-5:-2] == [f"from a thread {i}" for i in range(3)]
    assert re.fullmatch(r"Work 100% ▕█+▏ 12/12 · done in 00:01 · [\d.]+ it/s", shown[-2])
    assert shown[-1] == "after"
    assert sum("Work" in line for line in shown) == 1  # no frame left behind
    assert "\x1b[?25h" in raw.decode("utf-8")  # the cursor is given back
