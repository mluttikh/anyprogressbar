# Environment variables

| Variable | Effect |
|---|---|
| `ANYPROGRESSBAR` | Where bars show: `notebook` (the widget where anywidget is installed, else HTML), `widget`, `html`, `terminal`, `log` or `off`. A value that is none of these is ignored, with a warning. `set_renderer` in the code takes precedence. |
| `NO_COLOR` | Set (to anything): no colour on the terminal. |
| `CI` | Set: log lines, not a redrawn line, even when the output is a terminal. |
| `TERM=dumb` | Log lines: the terminal cannot redraw a line. |
| `WT_SESSION`, `ConEmuANSI=ON`, `TERM_PROGRAM=ghostty` | The progress of the first bar is also shown in the tab or the taskbar (Windows Terminal, ConEmu, Ghostty), when bars are drawn on that terminal. |

Where none of these says otherwise, bars show as the widget or HTML in a Jupyter kernel or
a marimo notebook, as a redrawn line when standard error is a terminal, and as log lines
everywhere else.
