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

## Known limits

- **A loop body that raises** cannot be seen by the iterator form: the bar ends as
  `stopped`, and only when the generator is collected (at once in CPython when nothing else
  holds the traceback; later in a notebook, which keeps the last traceback). The `with` form
  reports `failed` at once. A notebook renderer can close this gap with a hook that runs
  after each cell.
- **A parent's estimate** uses only its own updates, so an outer bar of a few slow steps
  has no time remaining for a long while. Weighted children (Foundation's pending units)
  would fix that; the tree allows it.
- **A slow item after many fast ones** is noticed late by the loop itself, since `gate` only
  adapts when it is reached. `bar.n` is stored on every item, so a renderer that draws from
  a timer still shows the true count.
