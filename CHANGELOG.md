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
- Log lines as the first renderer: a line every few seconds and one at the end, nothing for
  work that finishes within two seconds.
