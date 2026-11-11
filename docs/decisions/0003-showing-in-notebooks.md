# 0003: Showing in notebooks: what the host spike found

- Status: **partly implemented**, 11 November 2026: the plain HTML renderer (`notebook.py`,
  `tests/test_notebook.py`, and `tests/test_hosts.py`, which runs a real kernel and marimo).
  The widget followed in decision 0004, which changes one point below: a finished tree
  keeps no widget view. The spike's code is in `_scratch/spike/` (not in the repository).
- Tested: JupyterLab 4.6 (ipywidgets 8.1, anywidget 0.11) and marimo 0.25, in Chrome.
  **Not tested: VS Code notebooks and Colab.**

## Findings

- **Both hosts update a bar while its cell runs**, for an anywidget shown with
  `display(widget)` and for plain HTML replaced through an IPython display handle
  (`display(..., display_id=True)`, then `handle.update(...)`). Every value of a 20-step
  loop at about 7 updates a second reached the page.
- **marimo needs no path of its own**: it honours both IPython calls unchanged.
  (`mo.output.replace(mo.ui.anywidget(w))` works too.)
- **One widget can show a tree**: a parent and children added while it runs.
- **The browser can keep time itself**: a clock that ticks between updates, and a "no update
  for N s" notice during a 5 s item, with the kernel silent.
- **`display(widget)` leaves a poor record.** The stored output is the widget view and, as
  text, the object's repr. Without stored widget state a reader sees the repr.
- **A static picture can sit beside the widget view.** Display one bundle with the widget
  view, `text/html` and `text/plain` through a display handle, and rewrite it when the bar
  ends. While the cell runs JupyterLab shows the live widget; reopened with widget state it
  restores the widget; reopened without, or converted with nbconvert, it shows the HTML.
- **The native `<progress>` element is styled by the host** (marimo ignored the "done"
  colour). The bar should be drawn with elements of its own.

## Decision

- One widget per tree of bars.
- The widget is displayed through a display handle, with the static picture in the same
  output, rewritten at the end.
- The plain-HTML renderer and the static picture share their markup.
- No marimo-specific renderer; but a marimo-specific way to show HTML. marimo need not have
  IPython installed (the spike's environment happened to), so there the HTML goes through
  `mo.output.replace`. That replaces a cell's whole output, so the trees of one run are shown
  together: those since the last moment none was live.
- The HTML has inline styles only, no script and no style element, so it survives hosts that
  strip those. Colours are mid-tones that read on light and dark pages.
- The HTML renderer does not draw from a thread: output sent from another thread can land in
  the wrong cell. So its clock stands still during one slow item; the widget's will not.
- A bar is stalled only when nothing running under it has moved either.

## To do before relying on it

- Run the spike in VS Code and Colab.
- Measure a high update rate (comm traffic), and decide the widget's own interval.
- See what marimo stores for a finished bar.
