"""The notebook renderer without a widget: plain HTML, replaced in place.

In a Jupyter kernel the output is shown through an IPython display handle and updated
through it; in marimo, which need not have IPython, through `mo.output.replace`. Either way
what is stored in the notebook is ordinary HTML with a text version beside it, so a saved,
exported or mailed notebook shows how the work ended. (Decision 0003.)

It is one-way: the page only changes when the loop reports. The widget adds a clock that
ticks in the browser.
"""

from __future__ import annotations

import html
import sys
from typing import Any, Protocol

from anyprogressbar.state import Snapshot, Status
from anyprogressbar.terminal import lines, stalled, stats

# mid-tones that read on a light and on a dark page; the text beside the bar says the same
_COLOR = {
    Status.PENDING: "#868e96",
    Status.RUNNING: "#1c7ed6",
    Status.DONE: "#2f9e44",
    Status.FAILED: "#e03131",
    Status.STOPPED: "#e8930c",
}
_GRID = (
    "display:grid;grid-template-columns:fit-content(18em) max-content minmax(60px,240px) "
    "minmax(0,1fr);gap:4px 10px;align-items:center;font:13px/1.5 system-ui,-apple-system,"
    "'Segoe UI',sans-serif;max-width:860px"
)
_TRACK = "height:10px;border-radius:5px;background:rgba(128,128,128,.28);overflow:hidden"
_STRIPES = (
    "repeating-linear-gradient(-45deg,{c} 0 8px,transparent 8px 16px);opacity:.75"  # no total
)


def host() -> str | None:
    """The notebook the code runs in: "marimo", "ipython" (a Jupyter kernel), or None.
    Looks only at modules that are already imported."""
    marimo = sys.modules.get("marimo")
    if marimo is not None:
        try:
            if marimo.running_in_notebook():
                return "marimo"
        except Exception:
            pass
    ipython = sys.modules.get("IPython")
    if ipython is not None:
        try:
            shell = ipython.get_ipython()
        except Exception:
            shell = None
        if shell is not None and getattr(shell, "kernel", None) is not None:
            return "ipython"
    return None


def spoken(bar: Snapshot) -> str:
    """What a screen reader says for the bar's value."""
    return stats(bar).replace(" · ", ", ")


def _rows(bar: Snapshot, depth: int, out: list[str]) -> None:
    color = _COLOR[bar.status]
    fraction = bar.fraction
    name = html.escape(bar.desc or "Progress")
    percent = f"{100 * fraction:.0f}%" if fraction is not None else ""
    moving = fraction is None and not bar.status.finished
    if moving:
        inner = f"width:100%;height:100%;background:{_STRIPES.format(c=color)}"
        value = ""
    else:
        share = 100 * (1.0 if fraction is None else fraction)
        inner = f"width:{share:.2f}%;height:100%;background:{color}"
        value = f' aria-valuemin="0" aria-valuemax="100" aria-valuenow="{share:.0f}"'
    numbers = html.escape(stats(bar))
    if bar.status in (Status.FAILED, Status.STOPPED):
        numbers = f'<span style="color:{color};font-weight:600">{numbers}</span>'
    elif stalled(bar):
        numbers = f'<span style="color:{_COLOR[Status.STOPPED]};font-weight:600">{numbers}</span>'
    out.append(
        f'<span style="font-weight:600;padding-left:{16 * depth}px;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{name}</span>'
        f'<span style="text-align:right;font-variant-numeric:tabular-nums">{percent}</span>'
        f'<div role="progressbar" aria-label="{name}"{value} '
        f'aria-valuetext="{html.escape(spoken(bar))}" style="{_TRACK}">'
        f'<div style="{inner}"></div></div>'
        f'<span style="opacity:.8;font-variant-numeric:tabular-nums">{numbers}</span>'
    )
    for child in bar.children:
        if child.status is not Status.PENDING:
            _rows(child, depth + 1, out)


def to_html(root: Snapshot, *, note: str = "") -> str:
    """A tree of bars as HTML that stands on its own: inline styles, no script."""
    rows: list[str] = []
    _rows(root, 0, rows)
    if note:
        rows.append(f'<span style="grid-column:1/-1;opacity:.6;font-size:12px">{note}</span>')
    return f'<div style="{_GRID}">{"".join(rows)}</div>'


def to_text(root: Snapshot) -> str:
    """The same tree as text, for readers of the notebook file that show no HTML."""
    return "\n".join("".join(text for text, _ in row).rstrip() for row in lines(root, 100))


def bundle(root: Snapshot, *, note: str = "") -> dict[str, str]:
    return {"text/html": to_html(root, note=note), "text/plain": to_text(root)}


class Display(Protocol):
    """Where the pictures go: one output per root, replaced on each call."""

    def put(self, root_id: int, data: dict[str, str], *, final: bool) -> None: ...


class IPythonDisplay:
    """An output per root in the cell that is running, updated through its display handle."""

    def __init__(self) -> None:
        self._handles: dict[int, Any] = {}

    def put(self, root_id: int, data: dict[str, str], *, final: bool) -> None:
        from IPython.display import display

        handle = self._handles.get(root_id)
        if handle is None:
            handle = self._handles[root_id] = display(data, raw=True, display_id=True)
        else:
            handle.update(data, raw=True)
        if final:
            self._handles.pop(root_id, None)


class MarimoDisplay:
    """marimo replaces a cell's whole output, so the roots of one run are shown together:
    those since the last moment that none was live."""

    def __init__(self) -> None:
        self._shown: dict[int, Any] = {}  # HTML, or something else marimo can show (a widget)
        self._live: set[int] = set()

    def put(self, root_id: int, data: dict[str, str], *, final: bool) -> None:
        self.show(root_id, data["text/html"], final=final)

    def show(self, root_id: int, item: Any, *, final: bool) -> None:
        import marimo

        if root_id not in self._shown and not self._live:
            self._shown.clear()
        self._shown[root_id] = item
        self._live.add(root_id)
        if final:
            self._live.discard(root_id)
        items = list(self._shown.values())
        if all(isinstance(item, str) for item in items):
            marimo.output.replace(marimo.Html("".join(items)))
        else:
            marimo.output.replace(
                marimo.vstack([marimo.Html(i) if isinstance(i, str) else i for i in items])
            )


class NotebookRenderer:
    """Shows bars as plain HTML in a notebook, replaced in place. No widget, no script: what
    the notebook stores reads anywhere.

    Args:
        display: Where the pictures go. By default the notebook's (Jupyter or marimo).
        interval: The least time, in seconds, between two pictures of one bar.
        delay: Bars are first shown when they have run this long; work done sooner is never
            shown.
        note: A line under the first running bar (how to get the widget), gone from its
            last picture.
    """

    def __init__(
        self,
        display: Display | None = None,
        *,
        interval: float = 0.2,
        delay: float = 0.5,
        note: str = "",
    ) -> None:
        self._display = display
        self.interval = interval
        self.delay = delay
        self._note = note
        self._last: dict[int, float] = {}  # root id -> its elapsed time at the last picture

    def _put(self, root: Snapshot, *, final: bool, note: str = "") -> None:
        if self._display is None:
            self._display = MarimoDisplay() if host() == "marimo" else IPythonDisplay()
        self._display.put(root.id, bundle(root, note=note), final=final)

    def update(self, root: Snapshot) -> None:
        last = self._last.get(root.id)
        if last is None:
            if root.elapsed < self.delay:
                return
        elif root.elapsed - last < self.interval:
            return
        self._last[root.id] = root.elapsed
        self._put(root, final=False, note=self._note)

    def close(self, root: Snapshot) -> None:
        shown = self._last.pop(root.id, None) is not None
        if shown:
            self._note = ""  # said once
        quick = root.status is Status.DONE and root.elapsed < self.delay
        gone = root.status is Status.DONE and not root.leave
        if shown or not (quick or gone):
            self._put(root, final=True)
