# Switch from tqdm

anyprogressbar takes the part of tqdm's interface that most code uses, so most code changes
in its import only:

```python
from tqdm.auto import tqdm               # before
from anyprogressbar import progress as tqdm   # after
```

| tqdm | anyprogressbar |
|---|---|
| `tqdm(iterable, desc, total=, unit=, leave=, disable=)` | the same |
| `trange(n)` | `progress(range(n))` |
| `bar.update(n)`, `bar.close()`, `bar.refresh()` | the same |
| `bar.set_description(s)`, `bar.set_postfix(**values)` | the same |
| `bar.n`, `bar.total`, `bar.desc` | the same |
| `bar.n = x; bar.refresh()` | `bar.set(x)` (also tells the rate) |
| `mininterval=` | `min_interval=` |
| `tqdm.write(s)` | `print(s)`, or `write(s)` for a file of your own |
| `position=` for nested bars | not needed: a bar made inside another is its child |
| `logging_redirect_tqdm()` | not needed: logging goes above the bars |
| `tqdm.notebook`, `tqdm.auto` | not needed: bars show where the code runs |

## What is different

- **Nothing for quick work.** Work done within half a second shows no bar (two seconds
  for log lines).
- **No time remaining until it means something**, and rounded ("about 2 min left").
- **Bars end in words**: done, failed with the exception, or stopped.
- **Children go when done** (`leave=False` is the default for children), and a parent's
  time remaining counts its children.
- **On a terminal the bar goes to standard error**, as tqdm's does, and `print` goes above
  it.

## Not there (yet)

`unit_scale`, `unit_divisor` and `bar_format`; `set_postfix_str`; `reset`; `tqdm.pandas`
and `tqdm.contrib`; bars in other processes; a `position` for bars side by side that are
not nested.
