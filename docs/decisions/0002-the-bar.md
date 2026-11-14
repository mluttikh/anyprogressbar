# 0002: The bar: three ways in, a tree, three ways to end, and an estimate that can be absent

- Status: **implemented**, 11 November 2026.
- Changes: `bar.py` (`Bar`, `progress`), `state.py` (`Status`, `Snapshot`), `estimate.py`
  (`RateEstimator`), `format.py`; `tests/test_bar.py`, `tests/test_estimate.py`.

## Decision

- **`progress(...)` is `Bar`**, used three ways: around an iterable, as a `with` block
  updated by hand, or as a handle that is closed by hand. The total is the iterable's
  `len()`, else its length hint, else unknown.
- **tqdm's common subset** is kept by name: `update(n)`, `set_description`, `set_postfix`,
  `close`, `refresh`, and the attributes `n`, `total`, `desc`. Not a subclass, and not its
  keyword list.
- **A tree.** A bar made while another is current (inside its loop or its `with` block, per
  context) is its child; `parent=` says so explicitly, for threads. The root owns the lock
  and the renderer. A child that is done leaves the tree (`leave=False` by default for
  children); one that failed or stopped stays, so the reason stays visible.
- **Ends**: `done`; `failed` (an exception in a `with` block, or `fail(message)`);
  `stopped` (a `break`, Ctrl-C, or a block left short of its total). A bar never claims to
  be done when it is not: 40 of 100 and no error is `stopped`.
- **The hot path** of iteration is an add, a store and a comparison per item. The clock is
  read every `gate` items, with `gate` kept near half a `min_interval`'s worth of items
  (measured: about 35 ns per item over a bare loop, against about 60 ns for tqdm).
  `disable=True` returns the iterable's own iterator.
- **The rate** is an exponentially weighted average weighted by time (half-life 10 s),
  divided by the weight gathered so far, which removes the start-up bias. There is no rate,
  and so no time remaining, before 3 samples and 1 s. With nothing new for more than twice
  the last gap, the rate decays, so a stall lengthens the time remaining.
  `update(n, skip=True)` counts units as done without counting them towards the rate.
- **Time remaining is shown coarsely**: seconds, then 5 s steps, minutes, quarter hours.
- **A loop whose body raises ends as `failed`, at once**, in the iterator form too. The
  generator cannot see the body's exception: it is only closed, as after a `break`. So while
  a bar runs around a loop, `sys.monitoring` (Python 3.12) is asked for the exceptions that
  are raised and handled, per thread, and the generator looks at what is on its way up when
  it is closed. Tried on 3.12 to 3.15 with `break`, `return`, exceptions caught in the body,
  a `break` from a handler, exceptions from C, Ctrl-C and nested loops. It listens only
  while such a bar runs, and then makes each raised exception about 0.2 µs dearer. Where no
  tool id is free the bar ends as `stopped`, as before. (A first try, a hook after each
  notebook cell, came too late: the bar had already ended.)
  Several exceptions can be pending at once: a renderer raises and handles its own while a
  child that ended is drawn (marimo's output code does), and one that C code catches
  (`hasattr`, `getattr` with a default) is never said to be handled. Keeping only the
  newest made the outer loop of a failed pair `stopped` in marimo, and a `break` after such
  a lookup `failed`. So the newest few are kept, and the one that counts is the newest whose
  traceback has reached a frame that is running when the generator is closed.
- **A parent's time remaining counts the done part of its running children.** A child
  covers `weight` units of its parent (one by default: the inner loop of a nested loop).
  The estimator is only told of new ground, so nothing jumps when a child ends and its
  parent then counts the unit. The bar itself and its count still show whole units only.

## Known limits

- **A loop bar that is closed while an unrelated exception is on its way up** through a
  frame that is running (a generator kept in a variable and collected then) would be called
  failed.
- **A child that covers less than a unit** (two bars in a row inside one step) makes its
  parent's estimate too hopeful unless it is given a `weight`.

- **A slow item after many fast ones** is noticed late by the loop itself, since `gate` only
  adapts when it is reached. `bar.n` is stored on every item, so a renderer that draws from
  a timer still shows the true count.
