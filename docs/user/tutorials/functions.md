# Progress from your own functions

In this tutorial you put bars inside bars, write a function that shows its own progress
wherever it is called, and see how the outer bar estimates the time for the whole. It takes
about ten minutes. Do [your first progress bar](first-bar.md) first.

## 1. A loop inside a loop

Put a bar on both loops:

```python exec="on" source="above" html="true" session="functions"
import time

from anyprogressbar import progress
from docs_pictures import fake, show_html  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide

for epoch in progress(range(3), "Epochs"):
    for batch in progress(range(20), f"Batches of epoch {epoch}", unit="batches"):
        time.sleep(0.05)
print(show_html(at=1.5))  # markdown-exec: hide
```

That is the picture during the second epoch. The inner bar is drawn under the outer one,
indented, in the same output: a bar that starts while another one runs becomes its child.
You did not pass anything along.

When an epoch is done its bar goes, so a long job does not grow a long list. At the end
only the outer bar is left:

```python exec="on" html="true" session="functions"
for epoch in progress(range(3), "Epochs"):
    for batch in progress(range(20), f"Batches of epoch {epoch}", unit="batches"):
        time.sleep(0.05)
print(show_html())
```

## 2. The time remaining of the whole

Look at the first picture again: the outer bar has done one of its three epochs, yet it
says how long the rest will take, and the estimate does not jump when an epoch ends. The
outer bar counts how far its running child is: one epoch and a half done means half the
work done.

A child counts as one unit of its parent. When it covers more or less, say so with
`weight=`; see [bars inside bars](../how-to/nested.md).

## 3. A function that reports its own progress

This is what makes children useful. Write a function that puts a bar on its own work:

```python exec="on" source="above" html="true" session="functions"
def convert(name, pages=12):
    for page in progress(range(pages), f"Converting {name}", unit="pages"):
        time.sleep(0.05)

convert("report.pdf")
print(show_html())  # markdown-exec: hide
```

Called on its own, it has a bar of its own. Now call it from a loop that has a bar:

```python exec="on" source="above" html="true" session="functions"
for name in progress(["a.pdf", "b.pdf", "c.pdf"], "Files", unit="files"):
    convert(name)
print(show_html(at=0.9))  # markdown-exec: hide
```

The function's bar appears under the loop's. The function does not know who calls it, and
the caller does not know the function shows progress. A library can put bars on its slow
functions, and they fit into whatever bars the program has.

## 4. Keep a child

To keep a child's bar when it is done, pass `leave=True`:

```python exec="on" source="above" html="true" session="functions"
for name in progress(["train", "validate", "test"], "Datasets"):
    for row in progress(range(15), name, unit="rows", leave=True):
        time.sleep(0.04)
print(show_html())  # markdown-exec: hide
```

A child that failed or stopped is always kept, so that you can see where things went wrong.

## What you learned

- A bar that starts while another one runs is drawn under it, in the same output.
- Children that are done go, unless you pass `leave=True`.
- The parent's time remaining counts how far its children are.
- A function can show its own progress and still fit into its caller's bars.

From here, the [how-to guides](../how-to/index.md) have recipes for particular tasks.
