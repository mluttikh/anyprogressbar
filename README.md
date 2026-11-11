# anyprogressbar

Progress bars for Jupyter and marimo notebooks (an [anywidget](https://anywidget.dev)) and for
terminals, from one model. The loop reports progress; what shows it is chosen by where the
code runs.

Status: pre-alpha. The model, the terminal bar and log lines exist; the notebook bar and the
widget do not yet (a notebook gets log lines for now).

```bash
pip install "anyprogressbar[widget]"   # with the notebook widget (recommended)
pip install anyprogressbar             # no dependencies: scripts, CI, libraries
```

```python
from anyprogressbar import progress

for row in progress(rows, "Loading", unit="rows"):
    ...

with progress(total=100, desc="Steps") as bar:   # by hand; a failure in the block shows
    bar.update(10)
    bar.set_postfix(loss=0.42)

for epoch in progress(range(3), "Epochs"):       # a bar inside a bar is its child
    for batch in progress(batches, "Batches"):
        ...
```

A bar ends as `done`, `failed` or `stopped`, and gives no time remaining until the estimate
is worth showing. On a terminal it is redrawn in place; in a pipe, a file or a CI job it
becomes a line every few seconds. `ANYPROGRESSBAR=off` silences every bar, `log` and `terminal`
force one or the other, and `write(...)` prints above live bars.

The research behind the design is in
[docs/research/progress-bar-research.html](docs/research/progress-bar-research.html), and the
decisions in [docs/decisions](docs/decisions).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
```
