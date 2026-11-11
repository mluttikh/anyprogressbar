# 0001: One model, a ladder of renderers, and the widget as an extra

- Status: **partly implemented**, 11 November 2026. The model, the renderer protocol,
  `NullRenderer` and `LogRenderer` exist (`bar.py`, `state.py`, `render.py`); the terminal
  line, the notebook's HTML and the widget do not.
- Background: [the research report](../research/progress-bar-research.html), sections
  "Patterns the good ones share" and "Implications".

## Context

- The package shows progress as an anywidget in notebooks and falls back to the terminal.
  Scripts, CI jobs and libraries that only report progress should not install or import a
  widget stack.
- The libraries that age best keep reporting apart from showing (R's progressr, Julia's
  ProgressLogging, Foundation's `Progress`, Zig's `std.Progress`).

## Decision

- **The core imports nothing outside the standard library.** `anywidget` is the `widget`
  extra, and the README's install line is `pip install "anyprogressbar[widget]"`.
- **A bar knows nothing of how it is shown.** A tree's root hands a renderer an immutable
  `Snapshot` (plain data) at most every `min_interval` seconds (0.1) and at each start and
  end. A renderer is two methods, `update(root)` and `close(root)`.
- **Five renderers, chosen by where the code runs**: widget (notebook, extra installed),
  plain HTML through a display handle (notebook, no extra; says once how to get the widget),
  an animated terminal line (TTY), log lines (pipe, file, CI), nothing.
- **Order of choice**: the `renderer=` argument, then `set_renderer(...)`, then the
  `ANYPROGRESSBAR` variable, then detection. An unknown name in the variable warns and is
  ignored (configuration must not stop the work); an unknown name in code raises.
- **A renderer that raises is dropped** with one `RuntimeWarning`; the work goes on.
- **Log lines**: one every 5 s after a 2 s delay, one at the end. Work done within the
  delay prints nothing; a failure or a stop always prints.

## Not decided

- Detection itself (notebook kernel, marimo, TTY, `CI`, `NO_COLOR`, `TERM=dumb`).
- Whether the terminal line draws from the loop or from a timer thread (the recommendation
  is one shared, lazily started thread).
- Reporting from worker processes. Snapshots are plain data so that a queue can carry them.
