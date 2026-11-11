# One bar, many places to show it

## The model and its pictures

A bar knows how far some work is, and nothing about screens. When it moves, its outermost
bar (the root of its tree) makes a **snapshot**: plain, unchangeable data about itself and
its children at that moment. It hands snapshots to a **renderer**, at most ten times a
second, and at every start and end.

Everything that shows progress is a renderer: the terminal line, the notebook widget, the
plain HTML, log lines, nothing, or [one of your own](../how-to/renderer.md). A bar cannot
tell which one it has, so code that reports progress is the same everywhere: in a script, a
library, a notebook, a CI job.

## Chosen by where the code runs

| Where | Shown as |
|---|---|
| a Jupyter kernel or a marimo notebook, with anywidget | the widget |
| a notebook without anywidget, or whose page shows no widgets | plain HTML, replaced in place |
| a terminal (standard error is one, and not `TERM=dumb` or `CI`) | a line redrawn in place |
| anything else: a pipe, a file, a CI job | a line every few seconds |

Each step down keeps what the step above gave and drops what the place cannot do. The
choice is made when a bar of its own starts, and can be made for you:
`set_renderer(...)` in the code, else `ANYPROGRESSBAR=...` in the environment, else this
table.

## Trees, not positions

A bar made while another runs becomes its child. It is drawn in its parent's output, under
it, so nested work stays together however deep the calls go, and a function does not need
to be told where its bar belongs. Children that are done go, so a long job keeps a short
picture; children that failed or stopped stay, because that is where you need to look.

## Cheap enough to leave in

A loop over a bar costs about 35 ns per item: the bar counts, and reads the clock only
every so many items, as many as take about half the time between two pictures. A bar with
`disable=True` hands back the plain iterator and costs nothing. So bars can stay in library
code, and the caller decides whether they show.
