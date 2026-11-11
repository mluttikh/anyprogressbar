# What a bar says

## The line

A running bar, on a terminal (in a notebook the parts are the same, in columns):

```text
Loading  45% ▕█████████████▌                ▏ 27/60 · 00:01 · about 2 s left · 20 rows/s · loss=0.31
```

| Part | Says |
|---|---|
| `Loading` | the name (`desc`); "Progress" without one |
| `45%` | how much is done; absent without a total |
| the bar | the same, in eighths of a cell on a terminal; a block that runs back and forth without a total |
| `27/60` | done and total; `27 rows` without a total |
| `00:01` | time since the bar started |
| `about 2 s left` | the time remaining, once there is an estimate |
| `20 rows/s` | the rate, once there is an estimate |
| `loss=0.31` | values set with `set_postfix` |

When the bar has ended, the times say how it ended instead:

```text
Loading 100% ▕██████████████████████████████▏ 60/60 · done in 00:03 · 17.4 rows/s
Importing  60% ▕██████████████████            ▏ 6/10 · failed after 00:01: ValueError: row 7 has no date
Searching  41% ▕████████████▎                 ▏ 41/100 · stopped after 00:00
```

The rate after "done" is the average over the whole run.

## Numbers and times

| What | How | Examples |
|---|---|---|
| counts | whole numbers as they are; others with three significant digits, or none from 1000 | `3`, `2.5`, `1235` |
| elapsed time | to the second | `00:42`, `12:05`, `1:02:03` |
| time remaining | below 20 s to the second; then in 5 s steps; then in minutes; from an hour in quarter hours | `8 s`, `40 s`, `3 min`, `2 h 15 min` |
| rate | per second, else per minute, else per hour: whichever is at least 1; three significant digits, none from 100 | `227 it/s`, `2.4 it/min`, `1.5 it/h` |
| values | floats with three significant digits; others as they print | `loss=0.0123`, `epoch=4` |

## The time remaining and the rate

The rate is an average over time, in which the last ten seconds count as much as all
before them. There is none (and so no time remaining) until there are three reports and
one second. When nothing new comes for more than twice the last gap between reports, the
rate falls, so that a pause makes the time remaining longer. Work marked
`update(skip=True)` counts as done but not towards the rate.

A parent's time remaining counts the part of its running children that is done (each child
covers `weight` of the parent's units).

## When nothing moves

A running bar is **stalled** when nothing under it has moved for ten seconds, and for five
times the average time per unit so far (thirty seconds before the first unit). It then
says `no progress for 40 s` in place of the time remaining and the rate (in amber, in a
notebook).

## When a bar shows

| Where | First shown | While running | At the end |
|---|---|---|---|
| terminal | after 0.5 s | redrawn ten times a second | the last state stays in the scrollback |
| notebook widget | after 0.5 s | sent up to ten times a second; its clock ticks in the browser | replaced by plain HTML |
| notebook HTML | after 0.5 s | up to five times a second, only when the loop reports | stays as it is |
| log lines | after 2 s | a line every 5 s | one line |

Work that is done before it is first shown never shows. Work that fails or stops is always
shown. A child that is done goes from the picture unless it has `leave=True`; a child that
failed or stopped stays.

## Colours

| Status | Notebook | Terminal |
|---|---|---|
| running | blue bar | cyan bar |
| done | green bar | green bar |
| failed | red bar, numbers in red | red bar |
| stopped | amber bar, numbers in amber | yellow bar |
| stalled | numbers in amber | (the words say it) |

The terminal uses the sixteen basic colours, so that the terminal's theme decides the
contrast; `NO_COLOR` turns colour off. Where the stream cannot show block characters the
bar is drawn with `#` and `-`.

In a notebook each bar is a `progressbar` for screen readers, named after the bar, with the
same numbers as its value text.
