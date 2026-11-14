"""The notebook renderer with the widget: an anywidget that keeps time in the browser.

The kernel sends the tree of bars when it changes; the page draws it and, between two
pictures, moves the clocks on itself (js/src/widget.ts). So the elapsed time ticks and the
time remaining counts down during one slow item, and a stall is said, with no thread in the
kernel.

A tree is one widget. It is shown in an output that also holds the plain HTML and text
(`notebook.bundle`), and when the tree ends that output becomes the HTML and text alone and
the widget is closed: the notebook file then needs no widget state to show how the work
ended, and the kernel keeps no widget per finished bar. (Decision 0004.)

A page that shows no widgets (Jupyter started from an environment without anywidget) shows
that HTML instead, and it must not stand still: see the notes above `GRACE`.

anywidget is imported when the first bar is shown, never at `import anyprogressbar`.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any, Protocol

from anyprogressbar.notebook import MarimoDisplay, NotebookRenderer, bundle, host, raised
from anyprogressbar.state import Snapshot

_STATIC = Path(__file__).parent / "static"
_class: type | None = None

# Whether the page shows widgets cannot be asked: a kernel is told nothing of how its output
# is drawn. A page that shows none shows the HTML beside the widget's view, and that would
# stand still while the kernel feeds a widget nobody sees. So:
#
# - Each widget says "shown" when the page draws it. That answer is certain, but the kernel
#   reads it only once the running cell, and every cell queued behind it, has ended.
# - Until then the guess is whether the widgets' browser side is installed where the kernel
#   runs (`_assets`). Where it is, bars are widgets. Where it is not, a tree is a widget for
#   `GRACE` seconds (the page may answer) and plain HTML, replaced in place, after that; and
#   after `PROBES` such trees, HTML from the start.
# - If a widget was shown and the kernel has since been idle for a second with no answer,
#   the page shows no widgets: bars are HTML from then on, and say once why.
GRACE = 0.5
PROBES = 3
IDLE = 1.0
NO_WIDGETS_NOTE = (
    "This page shows no widgets, so this is the plain bar. For the one that keeps time by "
    "itself, install anywidget in the environment that Jupyter itself runs in."
)
_heard = False  # a widget said that it was drawn
_disproved = False  # the page had its chance to answer, and did not
_asked = False  # a widget was shown and not heard from
_asked_before_idle = False
_idle_since: float | None = None
_probed = 0
_unheard: list[Any] = []  # widgets no longer shown, kept open to hear from them yet
_assets_found: bool | None = None


def _on_message(_widget: Any, content: Any, _buffers: Any) -> None:
    global _heard, _disproved  # noqa: PLW0603
    if isinstance(content, dict) and content.get("shown"):
        _heard = True
        _disproved = False
        while _unheard:
            _unheard.pop().close()


def _assets() -> bool:
    """Whether the browser side of anywidget and of the widget manager is installed where
    the kernel runs. When Jupyter runs in the same environment, its page shows widgets."""
    global _assets_found  # noqa: PLW0603
    if _assets_found is None:
        try:
            from jupyter_core.paths import jupyter_path

            folders = [Path(folder) for folder in jupyter_path("labextensions")]
            _assets_found = any((f / "anywidget").is_dir() for f in folders) and any(
                (f / "@jupyter-widgets").is_dir() for f in folders
            )
        except Exception:
            _assets_found = False
    return _assets_found


def _cell_ended(now: float) -> None:
    global _idle_since, _asked_before_idle  # noqa: PLW0603
    _idle_since = now
    _asked_before_idle = _asked


def _cell_starts(now: float) -> None:
    """Messages are read in the order they came: an answer sent while the kernel was idle
    has been read by now."""
    global _disproved, _idle_since  # noqa: PLW0603
    waited = _idle_since is not None and now - _idle_since >= IDLE
    if _asked_before_idle and waited and not _heard:
        _disproved = True
    _idle_since = None


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
    """Where a tree's widget is shown, and its HTML in the same place."""

    heard: bool  # True where widgets are known to be shown, without asking

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        """Show the widget; `data` is the HTML and text for readers that have no widgets."""

    def put(self, root_id: int, data: dict[str, str], *, final: bool, raised: bool = False) -> None:
        """Put the HTML and text in the tree's place (the widget's, if it had one).
        `final`: the tree's last picture. `raised`: it ended with an exception."""


class IPythonWidgetDisplay:
    """An output per tree in the running cell: the widget's view with the HTML and text
    beside it, or the HTML and text alone."""

    heard = False

    def __init__(self) -> None:
        self._handles: dict[int, Any] = {}
        try:  # to know when the kernel was idle (`_cell_starts`)
            from IPython import get_ipython

            events = get_ipython().events
            events.register("post_run_cell", lambda _result: _cell_ended(time.monotonic()))
            events.register("pre_run_cell", lambda _info: _cell_starts(time.monotonic()))
        except Exception:
            pass

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        from IPython.display import display

        view = widget._repr_mimebundle_() or {}
        if isinstance(view, tuple):  # (data, metadata)
            view = view[0]
        self._handles[root_id] = display({**view, **data}, raw=True, display_id=True)

    def put(self, root_id: int, data: dict[str, str], *, final: bool, raised: bool = False) -> None:
        from IPython.display import display

        handle = self._handles.get(root_id)
        if handle is None:
            handle = self._handles[root_id] = display(data, raw=True, display_id=True)
        else:
            handle.update(data, raw=True)
        if final:
            self._handles.pop(root_id, None)


class MarimoWidgetDisplay:
    """In marimo the widget is one of the things in the cell's output (`MarimoDisplay`).
    marimo draws anywidgets itself, so there is nothing to wait for."""

    heard = True

    def __init__(self) -> None:
        self._outputs = MarimoDisplay()

    def show(self, root_id: int, widget: Any, data: dict[str, str]) -> None:
        import marimo

        self._outputs.show(root_id, marimo.ui.anywidget(widget), final=False)

    def put(self, root_id: int, data: dict[str, str], *, final: bool, raised: bool = False) -> None:
        self._outputs.put(root_id, data, final=final, raised=raised)


class WidgetRenderer:
    """Shows bars as a widget in a notebook, whose clock ticks in the browser. When the work
    ends, the output becomes the plain HTML that `NotebookRenderer` makes.

    Where it is not known that the page shows widgets, bars may be plain HTML instead (see
    the top of this module). If the widget cannot be made at all, they are HTML from then on.

    Args:
        display: Where the widget goes. By default the notebook's (Jupyter or marimo).
        interval: The least time, in seconds, between two pictures sent to the page.
        delay: Bars are first shown when they have run this long; work done sooner is never
            shown.
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
        self._opened: dict[int, float] = {}  # root id -> its elapsed time when first shown
        self._plain: set[int] = set()  # trees shown as HTML in the widget's place
        self._last: dict[int, float] = {}  # root id -> its elapsed time at the last picture
        # for trees that have no widget: after a failure to make one, and for the record of
        # a tree that ended before it was shown
        self._html = NotebookRenderer(interval=max(interval, 0.2), delay=delay)
        self._broken = False
        self._noted = False  # NO_WIDGETS_NOTE was shown
        self._noting: int | None = None  # the tree that shows it

    def _target(self) -> WidgetDisplay:
        if self._display is None:
            self._display = MarimoWidgetDisplay() if host() == "marimo" else IPythonWidgetDisplay()
        return self._display

    def _is_heard(self) -> bool:
        return _heard or self._target().heard

    def _open(self, root: Snapshot) -> None:
        global _probed, _asked  # noqa: PLW0603
        widget = widget_class()(tree=root.as_dict())
        try:
            widget.on_msg(_on_message)
            self._target().show(root.id, widget, bundle(root))
        except Exception:
            widget.close()
            raise
        if not self._is_heard():
            _probed += 1
            _asked = True
        self._widgets[root.id] = widget
        self._opened[root.id] = root.elapsed

    def _retire(self, widget: Any) -> None:
        """A widget that is no longer shown: closed, unless it may still be heard from."""
        if self._is_heard():
            widget.close()
        else:
            _unheard.append(widget)

    def _put_html(self, root: Snapshot) -> None:
        note = ""
        if _disproved and not self._noted:
            note = NO_WIDGETS_NOTE
            self._noting = root.id
        self._target().put(root.id, bundle(root, note=note), final=False)

    def update(self, root: Snapshot) -> None:
        widget = self._widgets.get(root.id)
        sure = self._is_heard()
        if root.id in self._plain:
            if root.elapsed - self._last[root.id] < self._html.interval:
                return
            self._put_html(root)
        elif widget is not None:
            waited = root.elapsed - self._opened[root.id] >= GRACE
            if not sure and (_disproved or (waited and not _assets())):
                # the page may be showing the HTML, which must then move
                del self._widgets[root.id]
                self._retire(widget)
                self._plain.add(root.id)
                self._put_html(root)
            elif root.elapsed - self._last[root.id] < self.interval:
                return
            else:
                widget.tree = root.as_dict()
        elif self._broken:
            self._html.update(root)
            return
        elif root.elapsed < self.delay:
            return
        elif not sure and (_disproved or (_probed >= PROBES and not _assets())):
            self._plain.add(root.id)
            self._put_html(root)
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
        self._opened.pop(root.id, None)
        self._last.pop(root.id, None)
        if self._noting == root.id:
            self._noted = True  # said once, and not kept in the record
        if widget is None and root.id not in self._plain:
            self._html.close(root)
            return
        self._plain.discard(root.id)
        try:
            self._target().put(root.id, bundle(root), final=True, raised=raised(root))
        finally:
            if widget is not None:
                self._retire(widget)
