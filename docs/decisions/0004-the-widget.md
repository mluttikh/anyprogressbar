# 0004: The widget

- Status: **implemented**, 11 November 2026 (`widget.py`, `js/`, `tests/test_widget.py`,
  `js/test/format.test.ts`, and a real kernel in `tests/test_hosts.py`).
- Seen working in JupyterLab 4.6 in Chrome, and run in marimo through `marimo export html`.
  **Not tested: VS Code notebooks, Colab, and marimo's live page.**

## Decision

- **One widget per tree of bars**, with one synced value: the tree as plain data
  (`Snapshot.as_dict()`). The page draws what it is sent; it sends nothing back.
- **The page keeps time between pictures.** Every quarter second it moves the running
  clocks on by the time since the last picture and makes the text again. So the elapsed
  time ticks, the time remaining counts down and a stall is said during one slow item, with
  no thread in the kernel. The fill itself never moves without a real value: it only eases
  between two that were sent.
- **The text is made in two places and must not differ**: `terminal.stats` in Python and
  `js/src/format.ts` in the page. `tests/fixtures/stats.json` holds cases made by Python
  that the JavaScript tests read; a Python test fails when the file is out of date. (It
  found two differences on its first run: how halves are rounded.)
- **When a tree ends, its output becomes the plain HTML and text, and the widget is
  closed.** This changes decision 0003, which kept the widget's view in the stored output.
  A finished bar has nothing left to animate; the notebook file then needs no widget state
  to show how the work ended; and the kernel does not keep a widget for every bar that ever
  ran (ipywidgets holds every open widget).
- **While it runs, the output holds the widget's view with the HTML and text beside it.**
  A host that cannot show widgets shows the HTML. Seen by accident: a JupyterLab without
  the widget manager showed the HTML bar, updated in place, with no error.
- **At most ten pictures a second** go to the page (the bar's own `min_interval`), each a
  few hundred bytes for a bar. Not measured beyond that.
- **Running bars have faint ribbing that moves backwards**, which makes a bar feel faster
  (Harrison, Yeo and Hudson 2010). Without a total a block runs along the track and claims
  no value. `prefers-reduced-motion` turns both off.
- **anywidget is imported when the first bar is shown**, never at `import anyprogressbar`.
- **"notebook" means the widget where anywidget is installed and the bundle is built, and
  the HTML bar where not**, which then says once how to get the widget. `widget` and `html`
  force one. If making or showing the widget fails, the bars are HTML from then on.
- **In marimo** the widget is shown with `mo.ui.anywidget` inside the cell's output, and
  replaced by HTML at the end, as elsewhere.
- **The bundle is built with esbuild from TypeScript** and is not committed; the wheel
  build makes it (hatch-jupyter-builder), as in anytrellis and anytimeline.

## Known limits

- A page opened while a bar runs counts the time from when it opened, not from when the
  picture was made.
- A tree that fails before it was shown is recorded through the HTML renderer; in marimo
  that is a separate group of outputs from the widgets of the same run.
- The colours are fixed mid-tones; they do not follow the host's theme.

## To do

- Run it in VS Code and Colab.
- Look at marimo's live page, and at what it stores for a finished bar.
