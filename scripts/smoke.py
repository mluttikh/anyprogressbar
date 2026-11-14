"""Smoke test of an installed anyprogressbar (the release job): the widget's bundle is in the
package, and a loop draws through each renderer, with only the package's own dependencies
(the `widget` extra for the widget).

    python -I scripts/smoke.py
"""

from __future__ import annotations

import io
from importlib import resources

import anyprogressbar
from anyprogressbar import LogRenderer, Status, progress
from anyprogressbar.notebook import NotebookRenderer, bundle
from anyprogressbar.terminal import TerminalRenderer


class Kept:
    """A notebook's output, kept."""

    def __init__(self) -> None:
        self.last: dict[str, str] = {}

    def put(self, root_id: int, data: dict[str, str], *, final: bool, raised: bool = False) -> None:
        self.last = data


def main() -> None:
    static = resources.files("anyprogressbar") / "static"
    for name in ("widget.js", "widget.css"):
        size = len((static / name).read_bytes())
        assert size > 1000, f"{name} is missing from the package or empty"

    log = io.StringIO()
    for _ in progress(range(3), "Log", renderer=LogRenderer(log, delay=0, interval=0)):
        pass
    assert "Log" in log.getvalue(), log.getvalue()
    assert "done" in log.getvalue(), log.getvalue()

    screen = io.StringIO()
    renderer = TerminalRenderer(screen, delay=0, interval=0, threaded=False, redirect=False)
    for _ in progress(range(3), "Terminal", renderer=renderer):
        pass
    assert "Terminal" in screen.getvalue(), screen.getvalue()

    kept = Kept()
    bar = progress(range(3), "Notebook", renderer=NotebookRenderer(kept, delay=0, interval=0))
    for _ in bar:
        pass
    assert bar.status is Status.DONE
    assert 'role="progressbar"' in kept.last["text/html"], kept.last
    assert "3/3" in bundle(bar.snapshot())["text/plain"]

    from anyprogressbar import widget

    if widget.available():
        shown = widget.widget_class()(tree=bar.snapshot().as_dict())
        assert shown.tree["desc"] == "Notebook"
        made = "the widget"
    else:
        made = "no widget (anywidget is not installed)"
    print(f"anyprogressbar {anyprogressbar.__version__} works, with {made}:", end=" ")
    print(", ".join(sorted(p.name for p in static.iterdir())))


if __name__ == "__main__":
    main()
