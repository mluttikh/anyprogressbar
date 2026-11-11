# Changelog

All notable changes to anyprogressbar. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The model: `progress(...)` (a `Bar`) wraps an iterable, works as a context manager, or is
  updated by hand; bars started inside another bar become its children; a bar ends as
  `done`, `failed` or `stopped`.
- A rate and time-remaining estimate that is absent until it is stable, and falls while
  nothing happens.
- Log lines for pipes, files and CI: a line every few seconds and one at the end, nothing
  for work that finishes within two seconds.
- The terminal renderer: bars redrawn in place, children as indented lines under their
  parent, colour by status, a moving block when there is no total, "no progress for …"
  during a stall, `#` and `-` where the stream has no block characters, and the last state
  left in the scrollback. A thread keeps the clock ticking through a slow item. Work done
  within half a second is not drawn.
- `write(...)` prints above live bars.
- The renderer is chosen by where the code runs (a terminal, or anything else), by
  `set_renderer`, or by `ANYPROGRESSBAR=terminal|log|off`. `CI`, `TERM=dumb` and `NO_COLOR`
  are respected.
- Progress in the tab or taskbar (OSC 9;4) in Windows Terminal, ConEmu and Ghostty.
