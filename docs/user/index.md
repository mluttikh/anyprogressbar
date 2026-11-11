# anyprogressbar

Progress bars for Jupyter and marimo notebooks and for terminals, from one model. Your loop
reports how far it is; where the code runs decides how that is shown: a widget in a
notebook, a line that is redrawn on a terminal, and a line every few seconds in a log.

```python exec="on" html="true"
import time
from anyprogressbar import progress
from docs_pictures import fake, show_replay  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide

for epoch in progress(range(3), "Epochs"):
    for batch in progress(range(40), f"Batches of epoch {epoch}", unit="batches"):
        time.sleep(0.05)
print(show_replay())  # markdown-exec: hide
```

```python
from anyprogressbar import progress

for epoch in progress(range(3), "Epochs"):
    for batch in progress(range(40), f"Batches of epoch {epoch}", unit="batches"):
        ...
```

## What it does

- **Says what you need, when you need it.** Nothing for work that is done in half a
  second. A time remaining only once the estimate is worth showing, and rounded the way
  people say it ("about 2 min left"). "No progress for 40 s" instead of a time remaining
  that has stopped being true ([what a bar says](reference/text.md)).
- **Ends in words.** A bar ends as **done**, **failed** (with the exception that ended it)
  or **stopped** (left early), in colour and in text, and stays as a record
  ([failures and interruptions](how-to/endings.md)).
- **Bars inside bars, without passing anything along.** A bar that starts while another
  one runs is its child; the parent's time remaining counts how far its children are
  ([tutorial](tutorials/functions.md)).
- **Keeps time in a notebook.** The widget's clock runs in the browser, so the bar keeps
  moving through one slow step. When the work ends it becomes plain HTML that stays in the
  saved notebook ([notebooks](how-to/notebooks.md)).
- **Lets you print.** On a terminal, `print` and logging go above the bars instead of
  through them ([print and log](how-to/print.md)).
- **Costs little.** About 35 ns per item of a loop, and nothing at all when switched off.
- **No dependencies** for scripts, CI jobs and libraries; the notebook widget is an extra
  ([install](how-to/install.md)).

```bash
pip install "anyprogressbar[widget]"   # with the notebook widget
pip install anyprogressbar             # no dependencies
```

**Example notebooks** to run yourself:
[getting started](https://github.com/mluttikh/anyprogressbar/blob/main/examples/getting_started.ipynb),
[bars inside bars](https://github.com/mluttikh/anyprogressbar/blob/main/examples/nested_bars.ipynb),
[how a bar ends, and stalls](https://github.com/mluttikh/anyprogressbar/blob/main/examples/endings_and_stalls.ipynb) and
[where bars show](https://github.com/mluttikh/anyprogressbar/blob/main/examples/where_bars_show.ipynb).

## Where to start

<div class="grid cards" markdown>

- **[Tutorials](tutorials/index.md)**: learn by making your first progress bar, step by
  step.
- **[How-to guides](how-to/index.md)**: recipes for a task: totals, nested work, failures,
  printing, notebooks, coming from tqdm.
- **[Reference](reference/index.md)**: every argument, and exactly what a bar says.
- **[Explanation](explanation/index.md)**: why bars behave the way they do.

</div>
