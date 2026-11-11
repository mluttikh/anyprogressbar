# Install anyprogressbar

anyprogressbar needs Python 3.12 or newer.

## With the notebook widget

For notebooks, install it with the `widget` extra:

=== "pip"

    ```bash
    pip install "anyprogressbar[widget]"
    ```

=== "uv"

    ```bash
    uv add "anyprogressbar[widget]"
    ```

The extra brings [anywidget](https://anywidget.dev), and with it the widget whose clock
ticks in the browser: the bar keeps moving through one slow step. Without it, bars in a
notebook are plain HTML that only changes when the loop reports.

!!! note "Install it where Jupyter runs too"

    The page that shows the notebook needs anywidget's browser side, which comes with the
    Python package. If Jupyter runs in an environment of its own (a `pipx` install, or
    `uv run --with jupyterlab jupyter lab`), add anywidget there as well:

    ```bash
    uv run --with jupyterlab --with anywidget jupyter lab
    ```

    Where the page shows no widgets, bars are the plain HTML ones, and the first one says
    so. See [bars in notebooks](notebooks.md).

## Without dependencies

For scripts, CI jobs and libraries, install it alone:

```bash
pip install anyprogressbar
```

It then needs nothing beyond the standard library. In a notebook it still shows bars, as
plain HTML.

## In a library

A library that reports progress should depend on `anyprogressbar` without the extra, and
leave the choice of the widget to the application or the user. Bars in a library nest under
whatever bars the program around it has ([tutorial](../tutorials/functions.md)).
