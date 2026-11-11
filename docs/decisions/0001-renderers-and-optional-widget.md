# 0001: One model, a ladder of renderers, and the widget as an extra

- Status: **partly implemented**, 11 November 2026. The model, the renderer protocol,
  `NullRenderer`, `LogRenderer` (`render.py`) and `TerminalRenderer` (`terminal.py`) exist,
  with detection of a terminal; the notebook HTML (0003) and the widget (0004) followed.
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

- **The terminal renderer draws from a thread**, one per renderer, started when a tree is
  live and ended when none is. A renderer with an `attach(root_id, source)` method is given
  a way to ask a root for a fresh picture, so clocks tick and a stall shows during one slow
  item. The thread asks outside its own lock: a bar holds its lock when it calls `update`.
- **One terminal renderer per stream**, shared by every tree: named renderers are made once.
- **A frame is written whole**, inside a synchronized update (mode 2026), leaving the last
  column free. The bar's width follows the terminal's width only, so it does not change as
  the numbers beside it do. A failure's reason takes the bar's place when both do not fit.
- **Drawn after half a second**; work done sooner leaves nothing. A done root's last line
  stays (`leave=False` erases it); a failed or stopped one always stays.
- **Detection so far**: standard error is a terminal, `TERM` is not `dumb`, and `CI` is not
  set, gives the terminal renderer; anything else log lines. `NO_COLOR` removes colour.
- **OSC 9;4** only where the terminal is known to take it (Windows Terminal, ConEmu,
  Ghostty); not iTerm2, where OSC 9 has meant a notification.

## Not decided

- Detection of a notebook kernel and of marimo (they get log lines until their renderers
  exist).
- The Windows console path (`_windows_ansi`) has not been run on Windows.
- Output the program prints itself while a bar is live goes above the bars (decision 0005).
- Reporting from worker processes. Snapshots are plain data so that a queue can carry them.
