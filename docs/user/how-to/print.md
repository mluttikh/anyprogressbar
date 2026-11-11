# Print and log while bars run

## On a terminal

Print and log as you always do. While bars are live, a line written to standard output,
standard error, or a logging handler that writes to them appears above the bars, and the
bars are drawn again under it:

```python
import logging
from anyprogressbar import progress

logging.basicConfig(format="%(levelname)s %(message)s")
log = logging.getLogger("job")

for i in progress(range(12), "Work"):
    ...
    if i == 6:
        print("printed")
        log.warning("logged")
```

The terminal shows, once the work is done:

```text
printed
WARNING logged
Work 100% ▕██████████████████████████████▏ 12/12 · done in 00:01 · 9.9 it/s
```

What it takes care of:

- **Logging handlers** set up before the bars (`logging.basicConfig()` keeps the stream it
  was given) are pointed above the bars too, and get their stream back when the bars end.
  Handlers that write to files, sockets, or are of another kind (such as rich's) are left
  alone.
- **Warnings** (`warnings.warn`) go above the bars.
- **A prompt** (`input("Name: ")`) has the screen to itself until it is answered; the bars
  come back after.
- **Threads** that print at the same time each get their lines whole.
- **Output to a file or a pipe** (`python job.py > out.txt`) is left alone: it cannot spoil
  the bars on the terminal.

Output that is written straight to the terminal, past Python's `sys.stdout` (a C library,
or a program started with `subprocess` that inherits the terminal), is not seen, and may
draw over the bars.

To switch it off, give the terminal renderer `redirect=False`:

```python
from anyprogressbar import set_renderer
from anyprogressbar.terminal import TerminalRenderer

set_renderer(TerminalRenderer(redirect=False))
```

## Into a file of your own

`write` prints above the bars too, and takes any stream:

```python
from anyprogressbar import write

with open("report.txt", "w") as report:
    for row in progress(rows, "Checking"):
        write(f"checked {row}", file=report)
```

## In a notebook

A bar in a notebook is an output of its own, above or below what the cell prints, so
printing and logging never touched it. Nothing to do.
