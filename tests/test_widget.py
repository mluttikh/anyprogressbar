"""The widget renderer, and the cases that keep the browser's text the same as Python's.

`python tests/test_widget.py` rewrites tests/fixtures/stats.json, which js/test/format.test.ts
reads.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from anyprogressbar import Snapshot, Status, progress, render
from anyprogressbar.notebook import NotebookRenderer
from anyprogressbar.state import Snapshot as _Snapshot
from anyprogressbar.terminal import stalled, stats

FIXTURE = Path(__file__).parent / "fixtures" / "stats.json"


def snap(**given: Any) -> Snapshot:
    values: dict[str, Any] = {
        "id": 1,
        "desc": "Load",
        "n": 0,
        "total": 100,
        "unit": "it",
        "status": Status.RUNNING,
        "elapsed": 0.0,
        "rate": None,
        "remaining": None,
        "since_progress": 0.0,
    }
    return _Snapshot(**(values | given))


def drawn(root: Snapshot) -> list[Snapshot]:
    """The bars a renderer draws: parents before children, pending ones left out."""
    out = [root]
    for child in root.children:
        if child.status is not Status.PENDING:
            out.extend(drawn(child))
    return out


def cases() -> list[dict[str, Any]]:
    running = snap(n=40, elapsed=20.0, rate=2.0, remaining=30.0, since_progress=0.4)
    child = snap(id=2, desc="Batches", n=3, total=8, elapsed=6.0, since_progress=1.0)
    named: dict[str, Snapshot] = {
        "just started": snap(),
        "running with an estimate": running,
        "the estimate rounds to the even neighbour": replace(running, remaining=12.5),
        "half a minute left": replace(running, remaining=27.5),
        "minutes left": replace(running, remaining=150.0),
        "hours left": replace(running, remaining=8000.0, rate=0.004),
        "a slow rate is per minute": replace(running, rate=0.04),
        "a fast rate has no decimals": replace(running, rate=1234.5),
        "over an hour": replace(running, elapsed=3725.0),
        "without a total": snap(total=None, n=1500, unit="rows", elapsed=3.0, rate=500.0),
        "a count that is not whole": snap(n=2.5, total=10.0, elapsed=5.0),
        "a large count that is not whole": snap(n=1234.5, total=5000.5, elapsed=5.0),
        "metrics": replace(running, metrics={"loss": "0.42", "lr": "0.001"}),
        "done": snap(n=100, status=Status.DONE, elapsed=50.0),
        "done at once": snap(n=100, status=Status.DONE),
        "failed with a reason": snap(
            n=4, total=10, status=Status.FAILED, elapsed=2.0, message="ValueError: bad row"
        ),
        "stopped": snap(n=7, total=10, status=Status.STOPPED, elapsed=61.0),
        "stalled": snap(n=10, elapsed=40.0, since_progress=25.0, rate=0.3, remaining=200.0),
        "not stalled when a unit is slow anyway": snap(n=2, elapsed=70.0, since_progress=20.0),
        "stalled before the first unit": snap(elapsed=31.0, since_progress=31.0),
        "not stalled while a child moves": snap(
            n=1, total=4, elapsed=60.0, since_progress=40.0, children=(child,)
        ),
        "stalled with its child": snap(
            n=1,
            total=4,
            elapsed=60.0,
            since_progress=40.0,
            children=(replace(child, since_progress=35.0, elapsed=40.0),),
        ),
        "a pending child is not drawn": snap(
            n=1, total=4, elapsed=5.0, children=(replace(child, status=Status.PENDING), child)
        ),
    }
    return [
        {
            "name": name,
            "bar": root.as_dict(),
            "stats": [stats(bar) for bar in drawn(root)],
            "stalled": [stalled(bar) for bar in drawn(root)],
        }
        for name, root in named.items()
    ]


def test_the_cases_the_browser_is_checked_against_are_what_python_says():
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == cases(), (
        "run `python tests/test_widget.py` and then `npm test` in js/"
    )


def test_a_snapshot_as_data_is_plain_json(clock):
    with progress(total=4, desc="Outer", clock=clock) as outer:
        outer.set_postfix(loss=0.5)
        inner = progress(total=2, desc="Inner").start()
        data = outer.snapshot().as_dict()
        inner.close()
    assert json.loads(json.dumps(data)) == data
    assert (data["status"], data["metrics"]) == ("running", {"loss": "0.5"})
    assert [c["desc"] for c in data["children"]] == ["Inner"]


# ---- the renderer, with the real widget class and a display that keeps what it is given ----

anywidget = pytest.importorskip("anywidget")
from anyprogressbar import widget as widget_module  # noqa: E402
from anyprogressbar.widget import WidgetRenderer  # noqa: E402

needs_bundle = pytest.mark.skipif(
    not widget_module.available(), reason="the bundle is not built: npm run build in js/"
)


class Shown:
    def __init__(self, *, broken: bool = False) -> None:
        self.widgets: dict[int, Any] = {}
        self.trees: dict[int, list[dict[str, Any]]] = {}
        self.finished: dict[int, dict[str, str]] = {}
        self.broken = broken

    def show(self, root_id, widget, data):
        if self.broken:
            raise RuntimeError("no comm")
        assert sorted(data) == ["text/html", "text/plain"]
        self.widgets[root_id] = widget
        self.trees[root_id] = [widget.tree]
        widget.observe(lambda change: self.trees[root_id].append(change["new"]), names="tree")

    def finish(self, root_id, data):
        self.finished[root_id] = data


class Puts:
    def __init__(self) -> None:
        self.puts: list[tuple[dict[str, str], bool]] = []

    def put(self, root_id, data, *, final):
        self.puts.append((data, final))


@needs_bundle
def test_a_tree_is_one_widget_that_is_sent_pictures_and_ends_as_html(clock):
    shown = Shown()
    renderer = WidgetRenderer(shown, delay=0.0)
    for epoch in progress(range(2), "Epochs", renderer=renderer, clock=clock):
        for _ in progress(range(4), f"Batches {epoch}"):
            clock.tick(1.0)
    ((root_id, widget),) = shown.widgets.items()
    trees = shown.trees[root_id]
    assert len(trees) > 4
    assert {t["desc"] for t in trees} == {"Epochs"}
    assert {c["desc"] for t in trees for c in t["children"]} == {"Batches 0", "Batches 1"}
    assert widget.comm is None  # closed: the kernel keeps no widget per finished bar
    record = shown.finished[root_id]
    assert record["text/plain"].startswith("Epochs 100%")
    assert 'role="progressbar"' in record["text/html"]


@needs_bundle
def test_pictures_are_limited_and_quick_work_makes_no_widget(clock):
    shown = Shown()
    renderer = WidgetRenderer(shown, interval=0.1, delay=0.5)
    for _ in progress(range(10), renderer=renderer, clock=clock):
        clock.tick(0.01)
    assert shown.widgets == {}
    assert shown.finished == {}
    with progress(total=2000, renderer=renderer, clock=clock) as bar:
        for _ in range(2000):
            clock.tick(0.001)  # two seconds in all
            bar.update()
    (trees,) = shown.trees.values()
    assert 10 <= len(trees) <= 17


@needs_bundle
def test_a_quick_failure_is_kept_as_html_without_a_widget(clock):
    shown, puts = Shown(), Puts()
    renderer = WidgetRenderer(shown, delay=0.5)
    renderer._html._display = puts
    with (
        pytest.raises(ValueError, match="bad row"),
        progress(total=10, desc="Import", renderer=renderer, clock=clock) as bar,
    ):
        bar.update(4)
        raise ValueError("bad row")
    assert shown.widgets == {}
    ((data, final),) = puts.puts
    assert final
    assert "4/10 · failed after 00:00: ValueError: bad row" in data["text/plain"]


@needs_bundle
def test_where_the_widget_cannot_be_shown_the_bars_are_html(clock):
    shown, puts = Shown(broken=True), Puts()
    renderer = WidgetRenderer(shown, delay=0.0)
    renderer._html._display = puts
    for _ in range(2):
        for _ in progress(range(4), "Load", renderer=renderer, clock=clock):
            clock.tick(1.0)
    assert shown.widgets == {}
    assert [final for _, final in puts.puts].count(True) == 2
    assert "Load 100%" in puts.puts[-1][0]["text/plain"]


def test_notebook_means_the_widget_where_there_is_one_and_html_with_a_note_where_not(
    monkeypatch,
):
    monkeypatch.setattr(render, "_shared", {})
    monkeypatch.setattr(widget_module, "available", lambda: True)
    assert isinstance(render._make("notebook"), WidgetRenderer)
    monkeypatch.setattr(render, "_shared", {})
    monkeypatch.setattr(widget_module, "available", lambda: False)
    plain = render._make("notebook")
    html = render._make("html")
    assert isinstance(plain, NotebookRenderer)
    assert isinstance(html, NotebookRenderer)
    assert "anyprogressbar[widget]" in plain._note
    assert html._note == ""


if __name__ == "__main__":
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(json.dumps(cases(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
