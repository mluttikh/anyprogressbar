"""The notebook renderer with the widget: an anywidget that keeps time in the browser.

The kernel sends the tree of bars when it changes; the page draws it and, between two
pictures, moves the clocks on itself (js/src/widget.ts). So the elapsed time ticks and the
time remaining counts down during one slow item, and a stall is said, with no thread in the
kernel.

A tree is one widget. It is shown in an output that also holds the plain HTML and text
(`notebook.bundle`), and when the tree ends that output becomes the HTML and text alone and
the widget is closed: the notebook file then needs no widget state to show how the work
ended, and the kernel keeps no widget per finished bar. (Decision 0004.)

anywidget is imported when the first bar is shown, never at `import anyprogressbar`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol

from anyprogressbar.notebook import MarimoDisplay, NotebookRenderer, bundle, host
from anyprogressbar.state import Snapshot

_STATIC = Path(__file__).parent / "static"
_class: type | None = None


def available() -> bool:
    """Whether the widget can be made: anywidget is installed, and the bundle is built."""
    if not (_STATIC / "widget.js").is_file():
        return False  # a source checkout without `npm run build`
    try:
        return importlib.util.find_spec("anywidget") is not None
    except (ImportError, ValueError):
        return False


def widget_class() -> type:
    """The widget's class, made on first use so that anywidget is imported only then."""
    global _class  # noqa: PLW0603
    if _class is None:
        import anywidget
        import traitlets

        class ProgressWidget(anywidget.AnyWidget):
            """A tree of bars, drawn in the browser."""

            _esm = _STATIC / "widget.js"
            _css = _STATIC / "widget.css"
            tree = traitlets.Dict().tag(sync=True)  # Snapshot.as_dict()

        _class = ProgressWidget
    return _class


class WidgetDisplay(Protocol):
    """Where a tree's widget is shown, and what is left when the tree ends."""

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        """Show the widget; `data` is the HTML and text for readers that have no widgets."""

    def finish(self, root_id: int, data: dict[str, str]) -> None:
        """Put the HTML and text in the widget's place."""


class IPythonWidgetDisplay:
    """An output per tree in the running cell: the widget's view with the HTML and text
    beside it, replaced by the HTML and text alone at the end."""

    def __init__(self) -> None:
        self._handles: dict[int, Any] = {}

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        from IPython.display import display

        view = widget._repr_mimebundle_() or {}
        if isinstance(view, tuple):  # (data, metadata)
            view = view[0]
        self._handles[root_id] = display({**view, **data}, raw=True, display_id=True)

    def finish(self, root_id: int, data: dict[str, str]) -> None:
        handle = self._handles.pop(root_id, None)
        if handle is not None:
            handle.update(data, raw=True)


class MarimoWidgetDisplay:
    """In marimo the widget is one of the things in the cell's output (`MarimoDisplay`)."""

    def __init__(self) -> None:
        self._outputs = MarimoDisplay()

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        import marimo

        self._outputs.show(root_id, marimo.ui.anywidget(widget), final=False)

    def finish(self, root_id: int, data: dict[str, str]) -> None:
        self._outputs.put(root_id, data, final=True)


class WidgetRenderer:
    """Shows bars as a widget in a notebook.

    display: where the widget goes; by default the host's (`notebook.host()`).
    interval: the least time, in seconds, between two pictures sent to the page.
    delay: a tree is first shown when it has run this long; done sooner, never.

    If the widget cannot be made or shown, the bars are plain HTML from then on.
    """

    def __init__(
        self,
        display: WidgetDisplay | None = None,
        *,
        interval: float = 0.1,
        delay: float = 0.5,
    ) -> None:
        self._display = display
        self.interval = interval
        self.delay = delay
        self._widgets: dict[int, Any] = {}
        self._last: dict[int, float] = {}  # root id -> its elapsed time at the last picture
        # for trees that have no widget: after a failure to make one, and for the record of
        # a tree that ended before it was shown
        self._html = NotebookRenderer(interval=max(interval, 0.2), delay=delay)
        self._broken = False

    def _open(self, root: Snapshot) -> None:
        if self._display is None:
            self._display = MarimoWidgetDisplay() if host() == "marimo" else IPythonWidgetDisplay()
        widget = widget_class()(tree=root.as_dict())
        try:
            self._display.show(root.id, widget, bundle(root))
        except Exception:
            widget.close()
            raise
        self._widgets[root.id] = widget

    def update(self, root: Snapshot) -> None:
        widget = self._widgets.get(root.id)
        if widget is not None:
            if root.elapsed - self._last[root.id] < self.interval:
                return
            widget.tree = root.as_dict()
        elif self._broken:
            self._html.update(root)
            return
        elif root.elapsed < self.delay:
            return
        else:
            try:
                self._open(root)
            except Exception:
                self._broken = True
                self._html.update(root)
                return
        self._last[root.id] = root.elapsed

    def close(self, root: Snapshot) -> None:
        widget = self._widgets.pop(root.id, None)
        self._last.pop(root.id, None)
        if widget is None:
            self._html.close(root)
            return
        try:
            assert self._display is not None
            self._display.finish(root.id, bundle(root))
        finally:
            widget.close()
