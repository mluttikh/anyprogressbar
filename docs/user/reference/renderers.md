# Renderers

A renderer turns snapshots of bars into something to look at. Bars that are given none use
the one `set_renderer` set, else the one the `ANYPROGRESSBAR` environment variable names,
else the one that suits where the code runs.

::: anyprogressbar.set_renderer

::: anyprogressbar.write

::: anyprogressbar.Renderer

::: anyprogressbar.LogRenderer

::: anyprogressbar.terminal.TerminalRenderer
    options:
      members: false

::: anyprogressbar.notebook.NotebookRenderer
    options:
      members: false

::: anyprogressbar.widget.WidgetRenderer
    options:
      members: false

::: anyprogressbar.NullRenderer
    options:
      members: false
