# anyprogressbar

Progress bars for Jupyter and marimo notebooks (an [anywidget](https://anywidget.dev)) and for
terminals, from one model. The loop reports progress; what shows it is chosen by where the
code runs.

Status: pre-alpha. The model, the notebook widget, a plain HTML bar for notebooks without
it, the terminal bar and log lines exist. Seen working in JupyterLab and marimo; not yet
tried in VS Code or Colab.

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
is worth showing. In a Jupyter or marimo notebook it is a widget whose clock ticks in the
browser, so it keeps moving through one slow item and says when nothing has come for a
while; when the work ends it becomes plain HTML, which stays in the saved notebook. Without
the `widget` extra it is that HTML throughout, replaced in place. On a terminal the bar is
redrawn in place; in a pipe, a file or a CI job it becomes a line every few seconds.
`ANYPROGRESSBAR=off` silences every bar, `log`, `terminal`, `notebook`, `widget` and `html`
force one, and `write(...)` prints above live bars.

Notebooks to run are in [`examples/`](examples/):
[getting started](examples/getting_started.ipynb), [bars inside bars](examples/nested_bars.ipynb),
[how a bar ends, and stalls](examples/endings_and_stalls.ipynb) and
[where bars show](examples/where_bars_show.ipynb).

The research behind the design is in
[docs/research/progress-bar-research.html](docs/research/progress-bar-research.html), and the
decisions in [docs/decisions](docs/decisions).

## Development

```bash
(cd js && npm install && npm run build)   # the widget's bundle; npm test for its tests
uv sync
uv run nbstripout --install               # once per clone: commit notebooks without outputs
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
```
