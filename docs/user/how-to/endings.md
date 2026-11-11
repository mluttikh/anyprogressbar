# Failures, interruptions and skipped work

```python exec="on" session="endings"
import time
from anyprogressbar import Status, progress
from docs_pictures import fake, show_html  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide
```

A bar ends in one of three ways, and says which in words as well as in colour:

| Ends as | When | Colour |
|---|---|---|
| **done** | the work finished: the loop ran out, or the `with` block ended with the total reached | green |
| **failed** | an exception ended it, or you called `fail()` | red, with the reason |
| **stopped** | it ended before the work was finished: a `break`, Ctrl-C, a `with` block that ended short | amber |

## When an exception ends the work

An exception in a `with` block, or in the body of a `for` loop over a bar, ends the bar as
failed, with the exception as the reason. The exception goes on as usual: the bar does not
catch it.

```python exec="on" source="above" html="true" session="endings"
try:
    for i in progress(range(30), "Parsing", unit="lines"):
        time.sleep(0.05)
        if i == 20:
            int("twenty")
except ValueError:
    pass
print(show_html())  # markdown-exec: hide
```

Bars inside it fail with it. Ctrl-C (`KeyboardInterrupt`) ends bars as stopped,
"interrupted".

## Ending a bar yourself

Say that it failed, and why:

```python exec="on" source="above" html="true" session="endings"
bar = progress(total=5, desc="Uploading").start()
time.sleep(0.6)
bar.update(2)
bar.fail("the server said no")
print(show_html())  # markdown-exec: hide
```

Or end it as stopped, with a reason:

```python
bar.close(Status.STOPPED, "cancelled by the user")
```

`close()` without arguments ends the bar as done if the total was reached (or there is
none), and as stopped otherwise.

## Work that was already done

Work that is skipped (found in a cache, done in an earlier run) still counts as done, but
it took no time, and counting it towards the rate would make the time remaining far too
hopeful. Mark it with `skip=True`:

```python exec="on" source="above" html="true" session="endings"
done_before = set(range(0, 60, 2))  # every other item was done in an earlier run

with progress(total=60, desc="Processing", unit="items") as bar:
    for item in range(60):
        if item in done_before:
            bar.update(skip=True)
            continue
        time.sleep(0.1)
        bar.update()
print(show_html(at=2.0))  # markdown-exec: hide
```

## When nothing happens for a while

When nothing has moved for ten seconds, and for five times what a unit took until then
(thirty seconds before the first unit), the bar says how long it has been quiet instead of
a time remaining that is no longer true:

```python exec="on" source="above" html="true" session="endings"
with progress(total=6, desc="Mostly quick", unit="files") as bar:
    for i in range(6):
        time.sleep(30 if i == 3 else 0.5)
        bar.update()
print(show_html(at=20.0))  # markdown-exec: hide
```

A bar whose child is still moving is not quiet. The terminal bar and the notebook widget
keep time by themselves, so they say this during the slow step; the plain HTML bar only
changes when the loop reports.
