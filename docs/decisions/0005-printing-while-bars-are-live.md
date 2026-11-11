# 0005: Printing and logging while bars are live

- Status: **implemented**, 11 November 2026 (`terminal.Redirect` and
  `TerminalRenderer`; `tests/test_terminal.py`, with a script run in a real
  pseudo-terminal).
- Applies to the terminal only. In a notebook a bar is an output of its own, and the log
  renderer only ever adds lines.

## Problem

A bar on a terminal is redrawn in place: the renderer moves the cursor up over its frame
and draws it again. A line printed by the program lands at the end of the frame, and the
next redraw erases it or draws through it (`...00:00printed`). Most programs print or log,
so `write(...)` alone, which knew about the frame, was not enough.

## Decision

- **While bars are live, the standard streams that are terminals are replaced** by a
  `Redirect`, which hands each finished line to the renderer: it erases the frame, writes
  the line to the stream it was meant for, and draws the frame again under it. A stream
  that goes to a file or a pipe (`script > out.txt`) is left alone: it cannot spoil the
  bars. The streams are put back when the last bar ends.
- **Logging handlers are pointed at it too.** A `StreamHandler` keeps the stream it was
  given (`logging.basicConfig()` takes `sys.stderr` once), so replacing `sys.stderr` does
  not reach it. Handlers of exactly that class that write to a replaced stream get the
  `Redirect` while bars are live and their own stream back after. Subclasses (files,
  sockets, rich's handler) are left alone. `warnings` and `logging.lastResort` look up
  `sys.stderr` each time and need nothing.
- **A line that is flushed before it is finished hands the screen over.** That is a prompt:
  `input()` flushes standard output before it reads. The frame is erased and not drawn
  again until the line is finished (the user's answer and its newline, or the next
  printed newline); if the bars end first, their last lines go under it.
- **Each thread's unfinished line is its own**, so lines printed from two threads stay
  whole, where a bare terminal would mix them (`print` writes the text and the newline
  separately).
- **During a burst of lines the frame is drawn at most every half `interval`** (twenty
  times a second); the thread draws it after the burst. A line on its own gets the bars
  back at once. Printing 300 000 lines in a pseudo-terminal took 1.4 µs a line without a
  bar and 2.6 µs with one (74 µs before this limit), with almost no more output.
- **Other code that replaces a stream meanwhile wins.** A stream is only put back if it is
  still the `Redirect`; a `Redirect` that is held somewhere after its bars ended passes
  everything straight through.
- **`redirect=False`** on `TerminalRenderer` turns it off. `write(...)` stays, for streams
  that are not redirected (a file of your own).

## Known limits

- Writes to `sys.stdout.buffer` or straight to file descriptor 1 or 2 (C extensions,
  subprocesses that inherit the terminal) are not seen.
- An unfinished line of another thread's is lost if the bars end before it is finished.
- Text with carriage returns (another progress bar) is passed on as it is, and may draw
  over the frame.
