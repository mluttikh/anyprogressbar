# A marimo app for the browser tests (js/test/browser/marimo.spec.ts): bars in marimo's live
# page, with its kernel running this project's Python package.

import marimo

app = marimo.App()


@app.cell
def _():
    import time

    from anyprogressbar import progress

    return progress, time


@app.cell
def _(progress, time):
    # one slow item: the kernel says nothing for six seconds
    with progress(total=4, desc="Slow") as bar:
        time.sleep(0.6)
        bar.update()
        time.sleep(6)
        bar.update(3)


@app.cell
def _(progress, time):
    for epoch in progress(range(2), "Epochs"):
        for i in progress(range(5), f"Batches {epoch}"):
            time.sleep(0.3)
            if epoch == 1 and i == 2:
                raise KeyError("id")


@app.cell
def _(progress, time):
    # loops one after another: each keeps its place in the output
    for _ in progress(range(4), "First"):
        time.sleep(0.3)
    for _ in progress(range(8), "Second"):
        time.sleep(0.3)


if __name__ == "__main__":
    app.run()
