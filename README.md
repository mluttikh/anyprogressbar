# anyprogressbar

Progress bars for Jupyter and marimo notebooks (an [anywidget](https://anywidget.dev)) and for
terminals, from one model. The loop reports progress; what shows it is chosen by where the
code runs.

Status: pre-alpha. The model and the log-line renderer exist; the terminal line, the notebook
bar and the widget do not yet.

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
is worth showing. `ANYPROGRESSBAR=off` silences every bar; `ANYPROGRESSBAR=log` writes lines.

The research behind the design is in
[docs/research/progress-bar-research.html](docs/research/progress-bar-research.html), and the
decisions in [docs/decisions](docs/decisions).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
```
