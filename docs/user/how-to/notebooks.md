# Bars in Jupyter, VS Code and marimo

## What you get

In a notebook a bar is an output of the cell, replaced in place as the work goes on.

- **With the `widget` extra** it is a widget: its clock ticks in the browser, so the
  elapsed time, the time remaining and a "no progress" notice keep up during a slow step,
  even while the kernel is busy with it.
- **Without it** the bar is plain HTML, which only changes when the loop reports. The first
  bar says once how to get the widget.

Either way, when the work ends the output becomes plain HTML with a text version beside it.
That is what the notebook saves: a saved, exported or converted notebook shows how the work
ended, without widget state and without Python.

Work done within half a second shows no bar at all.

Seen working in JupyterLab 4.6 and in marimo. VS Code and Colab have not been tried yet.

## marimo

Nothing to do: bars are part of the cell's output. Each loop's bar has its own place there,
so bars that run one after another in a cell are shown together, under whatever the cell
showed before them with `mo.output.append`.

When a cell raises, or is interrupted, marimo shows the error in place of the cell's
output, and the bars there go with it. So bars that end that way are also written to the
cell's console, as text, above the traceback: you still see how far the work got. (If you
catch the exception inside the cell, the bars are in the output and in the console.) An app
started with `marimo run` shows no console, so its viewers see neither.

## The bar does not move

**A line under the bar says the page shows no widgets.** The kernel has anywidget, but the
Jupyter that shows the page does not: it runs in an environment of its own. Install
anywidget there too, and restart Jupyter:

```bash
uv run --with jupyterlab --with anywidget jupyter lab
```

Until then bars are the plain HTML ones, which work, but stand still during a slow step.

**You want the plain HTML bar.** Choose it:

```python
from anyprogressbar import set_renderer

set_renderer("html")
```

or set `ANYPROGRESSBAR=html` before starting Jupyter.

## There is no bar

- The work was done within half a second: no bar is shown for quick work.
- `ANYPROGRESSBAR=off` is set, or `set_renderer("off")` was called.
- The bar was made with `disable=True`.
