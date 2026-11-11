# Your first progress bar

In this tutorial you put a progress bar on a loop, report progress by hand, show values
beside the bar, and see how a bar ends when something goes wrong. It takes about ten
minutes.

You need a notebook (JupyterLab, VS Code or marimo) or a terminal with Python, and
anyprogressbar installed; see [how to install it](../how-to/install.md). In a notebook,
type each step into a new cell and run it. On a terminal, put each step in a file and run
it with `python`. The bars on this page are what a notebook shows when the step is done.

## 1. Wrap a loop

Wrap what you loop over in `progress(...)`, with a name for the work and what is counted:

```python exec="on" source="above" html="true" session="first"
import time

from anyprogressbar import progress
from docs_pictures import fake, show_html, show_terminal  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide

for row in progress(range(60), "Loading", unit="rows"):
    time.sleep(0.05)
print(show_html())  # markdown-exec: hide
```

While the loop runs, the bar fills, the elapsed time ticks, and after a second or so a time
remaining and a rate appear. They wait until the estimate is worth showing: a guess from
the first two rows would jump about. Here is the bar halfway through:

```python exec="on" html="true" session="first"
for row in progress(range(60), "Loading", unit="rows"):
    time.sleep(0.05)
print(show_html(at=1.5))
```

When the loop ends, the bar stays as a record of what happened: how much, how long, how
fast. In a notebook that record is saved with the notebook.

On a terminal the same loop draws one line that is redrawn in place, and leaves its last
state in the scrollback:

```python exec="on" html="true" session="first"
for row in progress(range(60), "Loading", unit="rows"):
    time.sleep(0.05)
print(show_terminal())
```

## 2. Work that is quick shows nothing

Run a loop that is over at once:

```python
for row in progress(range(1000), "Too quick to show"):
    pass
```

Nothing appears. Work that is done within half a second gets no bar: it would only flash.
Work that fails is always shown, however quick.

## 3. Report progress by hand

Not every job is a loop over a list. Give the total, use the bar as a `with` block, and say
how much more is done with `update`:

```python exec="on" source="above" html="true" session="first"
sizes = [120, 40, 300, 80, 260, 200]

with progress(total=sum(sizes), desc="Downloading", unit="MB") as bar:
    for size in sizes:
        time.sleep(size / 300)
        bar.update(size)
print(show_html())  # markdown-exec: hide
```

The bar ends when the block does.

## 4. Show values beside the bar

`set_postfix` puts values of your own after the numbers. Each call replaces the last ones:

```python exec="on" source="above" html="true" session="first"
with progress(total=40, desc="Training", unit="steps") as bar:
    for step in range(40):
        time.sleep(0.08)
        bar.update()
        bar.set_postfix(loss=1 / (step + 1), lr=0.001)
print(show_html())  # markdown-exec: hide
```

## 5. See a bar fail

Make the work fail halfway:

```python exec="on" source="above" html="true" session="first"
try:
    with progress(total=10, desc="Importing", unit="files") as bar:
        for i in range(10):
            time.sleep(0.15)
            if i == 6:
                raise ValueError("row 7 has no date")
            bar.update()
except ValueError:
    pass
print(show_html())  # markdown-exec: hide
```

The bar stops where the work stopped, turns red, and says why. The exception itself goes on
as usual (here the `try` catches it, so that the rest of the tutorial runs). The same
happens with a `for` loop around a bar: an exception in the loop's body ends the bar as
failed.

Leave a loop early and the bar ends as **stopped**:

```python exec="on" source="above" html="true" session="first"
for i in progress(range(100), "Searching"):
    time.sleep(0.02)
    if i == 40:
        break
print(show_html())  # markdown-exec: hide
```

## What you learned

- `progress(iterable, "name", unit=...)` puts a bar on a loop.
- `with progress(total=..., desc=...) as bar:` and `bar.update(n)` report progress by hand.
- `bar.set_postfix(...)` shows values beside the bar.
- A bar ends as done, failed or stopped, and says so.

Next: [progress from your own functions](functions.md).
