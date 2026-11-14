from __future__ import annotations

import re
import sys
import types
from typing import Any

import pytest

from anyprogressbar import progress, render
from anyprogressbar.notebook import MarimoDisplay, NotebookRenderer, host, to_html, to_text


class Outputs:
    """A display that keeps each root's pictures."""

    def __init__(self) -> None:
        self.puts: list[tuple[int, dict[str, str], bool]] = []
        self.raised: list[int] = []  # the roots whose last picture said they ended raising

    def put(self, root_id, data, *, final, raised=False):
        self.puts.append((root_id, data, final))
        if raised:
            self.raised.append(root_id)

    @property
    def html(self) -> str:
        return self.puts[-1][1]["text/html"]

    @property
    def text(self) -> str:
        return self.puts[-1][1]["text/plain"]


def notebook(outputs, **given) -> NotebookRenderer:
    options: dict[str, Any] = {"delay": 0.0} | given
    return NotebookRenderer(outputs, **options)


def bars(markup: str) -> list[dict[str, str]]:
    """The progressbar elements of some HTML, as their attributes and fill."""
    found = []
    for tag, fill in re.findall(r'<div (role="progressbar"[^>]*)><div style="([^"]*)">', markup):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        width = re.search(r"width:([\d.]+)%", fill)
        found.append(attrs | {"width": width.group(1) if width else "", "fill": fill})
    return found


def test_a_bar_is_one_output_that_is_replaced_and_ends_as_a_record(clock):
    out = Outputs()
    for _ in progress(range(40), "Loading", unit="files", renderer=notebook(out), clock=clock):
        clock.tick(0.5)
    ids = {root_id for root_id, _, _ in out.puts}
    assert len(ids) == 1  # one output, replaced
    assert [final for _, _, final in out.puts].count(True) == 1
    assert out.puts[-1][2]
    assert out.text == "Loading 100% ▕█████████████████████████▏ 40/40 · done in 00:20 · 2 files/s"
    (bar,) = bars(out.html)
    assert bar["aria-label"] == "Loading"
    assert bar["aria-valuenow"] == "100"
    assert bar["aria-valuetext"] == "40/40, done in 00:20, 2 files/s"
    assert "#2f9e44" in bar["fill"]  # done: green
    assert "<script" not in out.html
    assert "<style" not in out.html


def test_pictures_are_limited_to_five_a_second(clock):
    out = Outputs()
    with progress(total=1000, renderer=notebook(out), clock=clock) as bar:
        for _ in range(1000):
            clock.tick(0.002)  # two seconds in all
            bar.update()
    assert 9 <= len(out.puts) <= 12


def test_work_done_within_the_delay_shows_nothing_and_a_quick_failure_does(clock):
    out = Outputs()
    renderer = notebook(out, delay=0.5)
    for _ in progress(range(10), renderer=renderer, clock=clock):
        clock.tick(0.01)
    assert out.puts == []
    with (
        pytest.raises(RuntimeError),
        progress(total=10, desc="Import", renderer=renderer, clock=clock) as bar,
    ):
        bar.update(4)
        raise RuntimeError("bad row")
    assert out.text.endswith("4/10 · failed after 00:00: RuntimeError: bad row")
    (failed,) = bars(out.html)
    assert (failed["aria-valuenow"], failed["width"]) == ("40", "40.00")
    assert "#e03131" in failed["fill"]
    assert "failed after 00:00: RuntimeError: bad row</span>" in out.html  # in words, in colour


def test_children_are_rows_in_the_same_output(clock):
    out = Outputs()
    seen = None
    for epoch in progress(range(2), "Epochs", renderer=notebook(out), clock=clock):
        for i in (inner := progress(range(4), f"Batches {epoch}")):
            clock.tick(1.0)
            if (epoch, i) == (1, 1):
                inner.refresh()
                seen = out.html
    assert seen is not None
    outer, child = bars(seen)
    assert (outer["aria-label"], outer["width"]) == ("Epochs", "50.00")
    assert (child["aria-label"], child["width"]) == ("Batches 1", "25.00")
    assert "padding-left:16px" in seen
    assert [b["aria-label"] for b in bars(out.html)] == ["Epochs"]


def test_without_a_total_the_bar_is_striped_and_claims_no_value(clock):
    out = Outputs()
    with progress(desc="Scanning", unit="rows", renderer=notebook(out), clock=clock) as bar:
        clock.tick(1)
        bar.update(100)
        (running,) = bars(out.html)
        assert "aria-valuenow" not in running
        assert running["aria-valuetext"] == "100 rows, 00:01"
        assert "repeating-linear-gradient" in running["fill"]
    (done,) = bars(out.html)
    assert (done["aria-valuenow"], done["width"]) == ("100", "100.00")


def test_names_and_messages_are_escaped(clock):
    out = Outputs()
    bar = progress(total=2, desc='<b>"x" & y</b>', renderer=notebook(out), clock=clock).start()
    bar.fail("<script>alert(1)</script>")
    assert "<b>" not in out.html
    assert "<script>" not in out.html
    assert "&lt;b&gt;&quot;x&quot; &amp; y&lt;/b&gt;" in out.html


def test_the_note_about_the_widget_is_said_once_and_not_kept(clock):
    out = Outputs()
    renderer = notebook(out, note="get the widget")
    with progress(total=2, renderer=renderer, clock=clock) as bar:
        bar.update(1)
        assert "get the widget" in out.html
        bar.update(1)
    assert "get the widget" not in out.html  # the record does not carry it
    with progress(total=2, renderer=renderer, clock=clock) as bar:
        bar.update(1)
        assert "get the widget" not in out.html
        bar.update(1)


def test_a_bar_that_is_not_left_ends_as_its_last_picture_only_if_it_was_shown(clock):
    out = Outputs()
    with progress(total=2, leave=False, renderer=notebook(out, delay=5), clock=clock) as bar:
        bar.update(2)
    assert out.puts == []


def test_html_and_text_of_a_snapshot(clock):
    bar = progress(total=8, desc="Copy", clock=clock).start()
    clock.tick(2)
    bar.update(2)
    snap = bar.snapshot()
    assert to_text(snap) == "Copy  25% ▕██████▎                  ▏ 2/8 · 00:02"
    assert to_html(snap).startswith('<div style="display:grid')
    bar.close()


class Cell:
    """A marimo cell's output, as marimo keeps it: a list that `mo.output` functions change."""

    def __init__(self) -> None:
        self.items: list[Any] = []

    def __len__(self) -> int:
        return len(self.items)

    def replace_at_index(self, item, idx):
        if idx > len(self.items):
            raise IndexError(idx)
        if idx == len(self.items):
            self.items.append(item)
        else:
            self.items[idx] = item


def fake_marimo(monkeypatch, cell: Cell | None) -> list[Any]:
    """marimo, running a cell whose output is `cell` (None: it cannot be read). Returns what
    `mo.output.replace` was given."""
    from anyprogressbar import notebook as notebook_module

    replaced: list[Any] = []

    def place(item, idx):
        assert cell is not None, "without the cell's output nothing is put in its place"
        cell.replace_at_index(item, idx)

    fake = types.SimpleNamespace(
        Html=lambda markup: markup,
        vstack="".join,
        output=types.SimpleNamespace(replace=replaced.append, replace_at_index=place),
        running_in_notebook=lambda: True,
    )
    monkeypatch.setitem(sys.modules, "marimo", fake)
    monkeypatch.setattr(notebook_module, "_cell_outputs", lambda: cell)
    return replaced


def test_in_marimo_each_tree_has_its_place_and_the_cells_other_output_stays(monkeypatch):
    cell = Cell()
    fake_marimo(monkeypatch, cell)
    assert host() == "marimo"
    cell.items.append("<note>")  # mo.output.append in the cell, before the loops
    display = MarimoDisplay()
    display.put(1, {"text/html": "<a1>"}, final=False)
    display.put(1, {"text/html": "<a2>"}, final=True)
    display.put(2, {"text/html": "<b1>"}, final=False)  # the next loop: the first one stays
    cell.items.append("<chart>")  # something the loop shows
    display.put(2, {"text/html": "<b2>"}, final=True)
    assert cell.items == ["<note>", "<a2>", "<b2>", "<chart>"]
    # the cell runs again: a new output
    cell = Cell()
    fake_marimo(monkeypatch, cell)
    display.put(3, {"text/html": "<c1>"}, final=False)
    assert cell.items == ["<c1>"]
    # the output is cleared while the tree runs: it goes at the end again
    cell.items.clear()
    display.put(3, {"text/html": "<c2>"}, final=True)
    assert cell.items == ["<c2>"]


def test_where_the_cells_output_cannot_be_read_the_trees_of_one_run_are_shown_together(
    monkeypatch,
):
    replaced = fake_marimo(monkeypatch, None)
    display = MarimoDisplay()
    display.put(1, {"text/html": "<a1>"}, final=False)
    display.put(2, {"text/html": "<b1>"}, final=False)
    display.put(1, {"text/html": "<a2>"}, final=True)
    assert replaced[-1] == "<a2><b1>"
    display.put(2, {"text/html": "<b2>"}, final=True)
    display.put(3, {"text/html": "<c1>"}, final=False)  # a new run: the old ones are let go
    assert replaced[-1] == "<c1>"


def test_the_last_picture_says_whether_the_tree_ended_with_an_exception(clock):
    out = Outputs()
    renderer = notebook(out)
    with pytest.raises(ValueError, match="bad row"):
        for i in progress(range(10), "Fails", renderer=renderer, clock=clock):
            clock.tick(1.0)
            if i == 3:
                raise ValueError("bad row")
    with pytest.raises(KeyboardInterrupt):
        for _ in progress(range(10), "Interrupted", renderer=renderer, clock=clock):
            clock.tick(1.0)
            raise KeyboardInterrupt
    for i in progress(range(10), "Left", renderer=renderer, clock=clock):
        clock.tick(1.0)
        if i == 3:
            break
    for _ in progress(range(3), "Done", renderer=renderer, clock=clock):
        clock.tick(1.0)
    finals = [root_id for root_id, _, final in out.puts if final]
    assert len(finals) == 4
    assert out.raised == finals[:2]


def test_in_marimo_a_tree_that_ended_with_an_exception_is_also_in_the_console(monkeypatch, capsys):
    """marimo puts a raising cell's error in place of its output; its console stays."""
    cell = Cell()
    fake_marimo(monkeypatch, cell)
    display = MarimoDisplay()
    picture = {"text/html": "<a>", "text/plain": "Import  40% ▕██▏ 4/10 · failed after 00:01"}
    display.put(1, picture, final=False)
    display.put(1, picture, final=True)  # ended otherwise: the output keeps it
    assert capsys.readouterr().err == ""
    display.put(2, picture, final=True, raised=True)
    assert cell.items == ["<a>", "<a>"]
    assert capsys.readouterr().err == picture["text/plain"] + "\n"


def test_a_jupyter_kernel_is_detected_and_a_plain_ipython_shell_is_not(monkeypatch):
    monkeypatch.delitem(sys.modules, "marimo", raising=False)
    shell = types.SimpleNamespace(kernel=object())
    monkeypatch.setitem(sys.modules, "IPython", types.SimpleNamespace(get_ipython=lambda: shell))
    assert host() == "ipython"
    assert render.detect() == "notebook"
    shell.kernel = None  # ipython in a terminal
    assert host() is None
    monkeypatch.setitem(sys.modules, "IPython", types.SimpleNamespace(get_ipython=lambda: None))
    assert host() is None
