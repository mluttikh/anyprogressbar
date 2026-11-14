# 0004: The widget

- Status: **implemented**, 11 November 2026 (`widget.py`, `js/`, `tests/test_widget.py`,
  `js/test/format.test.ts`, and a real kernel in `tests/test_hosts.py`).
- Browser tests, 14 November 2026 (`js/test/browser`, Playwright): the widget's module in
  Chromium, Firefox and WebKit on a clock the test moves; then in a real JupyterLab 4.6 and
  in marimo's live page (`marimo run`), and the documentation's replay, in Chromium.
  **Not tested: VS Code notebooks and Colab.**

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
  A page that cannot show widgets shows the HTML.
- **That HTML must not stand still.** It did at first: in a JupyterLab started from an
  environment without anywidget (`uv run --with jupyterlab jupyter lab`), the bar appeared
  at its first value and jumped to 100% at the end, because the kernel fed a widget that
  nobody saw. A kernel is not told how its output is drawn, so it goes by three things:
  - Each widget says "shown" when the page draws it. That is certain, but the kernel reads
    it only when the running cell, and every cell queued behind it, has ended (seen in
    JupyterLab 4.6 with ipykernel 7.4). So it is no use for the first cell, or for Run All.
  - Until then, the guess is whether the browser side of anywidget and of the widget
    manager is installed where the kernel runs. Where it is, bars are widgets. Where it is
    not, a tree is a widget for half a second, in case the page answers, and HTML replaced
    in place after that; after three such trees, HTML from the start.
  - If a widget was shown and the kernel has since been idle for a second with no answer,
    the page shows no widgets: bars are HTML from then on, and the first says once why and
    what to install. A late answer undoes this.
  Seen in both JupyterLabs: widgets throughout where they can be shown, HTML that moves
  where they cannot.
- **At most ten pictures a second** go to the page (the bar's own `min_interval`), each a
  few hundred bytes for a bar. Not measured beyond that.
- **The track and the text share the width a third and two thirds**, the track at least
  60 px, and the text wraps. The track had a fixed largest width at first; on a page
  narrower than about 600 px it took the room first and left the text a column a word wide
  (found by the browser tests). The plain HTML has the same grid.
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

- Where the kernel's environment has the widgets' browser side and Jupyter's does not, the
  first cell's bars stand still (and all of them under Run All), until the kernel has been
  idle once. `ANYPROGRESSBAR=html` avoids it.

- A page opened while a bar runs counts the time from when it opened, not from when the
  picture was made.
- A tree that fails before it was shown is recorded through the HTML renderer; in marimo
  that is a separate group of outputs from the widgets of the same run.
- The colours are fixed mid-tones; they do not follow the host's theme.
- **In marimo, the bars of a cell that raises are lost**: marimo puts the cell's error in
  place of its output, which held them (`marimo run` shows nothing there at all). Jupyter
  keeps both. A browser test expects them, and is marked as failing until they are kept.

## To do

- Run it in VS Code and Colab.
- Keep the failed bars of a marimo cell that raises (see Known limits).
