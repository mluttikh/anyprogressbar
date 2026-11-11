# Write a renderer of your own

A renderer is anything with two methods, `update(root)` and `close(root)`. It is given a
[`Snapshot`](../reference/snapshot.md): plain data about a bar and its children at one
moment. Use one to send progress somewhere else: a status page, a chat, a file, a metric.

```python exec="on" source="above" result="text" session="renderer"
import time
from anyprogressbar import progress
from docs_pictures import fake  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide

class Milestones:
    """Says when each quarter of the work is passed."""

    def __init__(self):
        self.said = 0

    def update(self, root):
        quarter = int(4 * (root.fraction or 0))
        if quarter > self.said:
            self.said = quarter
            print(f"{root.desc}: {25 * quarter}% after {root.elapsed:.1f} s")

    def close(self, root):
        print(f"{root.desc}: {root.status} ({root.n:.0f} of {root.total:.0f})")

for _ in progress(range(40), "Milestones", renderer=Milestones()):
    time.sleep(0.05)
```

## What it is given

- `update` is called when a bar starts, then at most every `min_interval` (0.1 s by
  default) while it moves, and when a child starts or ends.
- `close` is called once, when the bar of its own ends; `root.status` says how.
- Only the bar of its own (the root) calls the renderer; its children are in
  `root.children`.

A snapshot holds the numbers, not text. To say them as anyprogressbar does, use the
functions in `anyprogressbar.format`, or `anyprogressbar.terminal.stats(bar)` for the whole
line of numbers.

## Rules

- Keep it quick: it runs in the thread that does the work, inside the bar's lock.
- Don't raise. A renderer that raises is dropped with a `RuntimeWarning`, and the bar goes
  on without it: showing progress must never stop the work.
- To draw on a timer (so that a clock ticks while the work is busy), add an
  `attach(root_id, source)` method: `source()` returns a fresh snapshot of that root, and
  may be called from any thread.

## For every bar

```python
from anyprogressbar import set_renderer

set_renderer(Milestones())
```
