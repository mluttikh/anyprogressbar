# Choose where bars show

```python exec="on" session="where"
import time
from anyprogressbar import progress
from docs_pictures import fake, show_log  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide
```

By default bars show where the code runs: in a notebook, as the widget or plain HTML; on a
terminal, as lines redrawn in place; anywhere else (a pipe, a file, a CI job), as log
lines. [Why, and how it is decided](../explanation/renderers.md).

## For all bars, from the outside

Set the `ANYPROGRESSBAR` environment variable, without changing the code:

```bash
ANYPROGRESSBAR=off python job.py      # no bars at all
ANYPROGRESSBAR=log python job.py      # log lines, also on a terminal
```

It takes `notebook`, `widget`, `html`, `terminal`, `log` or `off`; see
[environment variables](../reference/environment.md).

## For all bars, from the code

```python
from anyprogressbar import set_renderer

set_renderer("log")    # or "terminal", "notebook", "widget", "html", "off"
set_renderer(None)     # back to choosing by where the code runs
```

`"terminal"` also works where the output is no terminal, such as a notebook's: there it
redraws one line, the top bar, and writes each finished tree whole at the end.

`set_renderer` also takes a renderer object, to set its options:

```python
from anyprogressbar import LogRenderer, set_renderer

set_renderer(LogRenderer(interval=30, delay=10))   # a line every 30 s, after 10 s
```

## Log lines

What a pipe or a CI job gets: a line every five seconds while the work runs, and one when
it ends; nothing for work done within two seconds. On standard error by default.

```python exec="on" source="above" html="true" session="where"
with progress(total=120, desc="Nightly import", unit="files") as bar:
    for i in range(120):
        time.sleep(0.15)
        bar.update()
print(show_log())  # markdown-exec: hide
```

## For one bar

Give it a renderer of its own, or switch it off. A switched-off bar costs nothing in the
loop:

```python
for row in progress(rows, "Only to the log", renderer=LogRenderer()):
    ...

for row in progress(rows, "Not shown", disable=True):
    ...
```

A library can pass `disable=not verbose` to let its caller decide.
