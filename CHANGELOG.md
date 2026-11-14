# Changelog

All notable changes to anyprogressbar. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The model: `progress(...)` (a `Bar`) wraps an iterable, works as a context manager, or is
  updated by hand; bars started inside another bar become its children; a bar ends as
  `done`, `failed` or `stopped`.
- A loop whose body raises ends its bar as `failed`, with the exception as the reason, also
  when the bar is wrapped around the loop and not a `with` block.
- A parent bar's time remaining counts how far its running children are (`weight=` says how
  many of the parent's units a child covers).
- A rate and time-remaining estimate that is absent until it is stable, and falls while
  nothing happens.
- Log lines for pipes, files and CI: a line every few seconds and one at the end, nothing
  for work that finishes within two seconds.
- The terminal renderer: bars redrawn in place, children as indented lines under their
  parent, colour by status, a moving block when there is no total, "no progress for …"
  during a stall, `#` and `-` where the stream has no block characters, and the last state
  left in the scrollback. A thread keeps the clock ticking through a slow item. Work done
  within half a second is not drawn.
- The notebook renderer without the widget: the bar as plain HTML, replaced in place in a
  Jupyter kernel (through a display handle) and in marimo. What the notebook stores is HTML
  and text, so a saved or exported notebook shows how the work ended. Each bar is a named
  `progressbar` for screen readers, and a failure is said in words as well as in colour. On
  a narrow page the bar gives up width before the text does. In marimo each tree has its own
  place in the cell's output, so loops one after another keep their bars, and what the cell
  showed with `mo.output.append` stays; and since marimo shows a raising cell's error in
  place of its output, bars that end with an exception are also written to the cell's
  console, above the traceback.
- The notebook widget (the `widget` extra, an anywidget): one widget for a tree of bars. Its
  clock ticks in the browser, so the elapsed time, the time remaining and a stall notice
  keep up during one slow item. When the work ends the output becomes the plain HTML and
  text, so the saved notebook needs no widget state. Used wherever anywidget is installed;
  without it the HTML bar says once how to get it. Where the notebook page cannot show
  widgets (Jupyter started from an environment without anywidget), the bar is the HTML one
  and says so once.
- On a terminal, what is printed or logged while bars are live goes above them, and a
  prompt for `input()` has the screen until it is answered. `write(...)` does the same for
  a stream of your own.
- Example notebooks in `examples/`, run by the tests.
- User documentation (Zensical): tutorials, how-to guides, reference and explanation. The
  examples in it run while it is built, and the bars shown are what they drew.
- The renderer is chosen by where the code runs (a notebook, a terminal, or anything else),
  by `set_renderer`, or by `ANYPROGRESSBAR=notebook|widget|html|terminal|log|off`. `CI`, `TERM=dumb` and `NO_COLOR`
  are respected.
- Progress in the tab or taskbar (OSC 9;4) in Windows Terminal, ConEmu and Ghostty.
