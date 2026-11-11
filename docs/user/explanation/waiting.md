# Why bars wait, round and go quiet

A progress bar has one job: to let you decide what to do while you wait. Wait, get a
coffee, or stop the work because something is wrong. Most choices anyprogressbar makes
follow from that, and from what is known about how people experience waiting. The research
behind them is collected in
[a report](https://github.com/mluttikh/anyprogressbar/blob/main/docs/research/progress-bar-research.html).

## Nothing for quick work

Below a second people do not need to be told anything is happening, and a bar that appears
for a moment and vanishes is noise. Bars show after half a second, log lines after two:
in a log every line stays, so it should be worth keeping. Work that fails is always shown,
however quick.

## A time remaining only when it means something

People want to know how much is done, and how long the rest will take. A time remaining
that jumps from 2 seconds to 40 minutes and back is worse than none: it teaches you to
ignore it. So there is no estimate until there are a few reports and a second has passed,
and the estimate is an average over time in which recent work counts most (a time-weighted
moving average, as Rust's indicatif uses), corrected for having little data at first.

## Rounded the way people say it

"About 2 min left", not "00:01:53": the last digits of an estimate are not true, and
showing them suggests they are. Times far away are rounded more. The elapsed time is exact,
because it is.

## Quiet when it is not true any more

When work stalls, a time remaining that keeps counting down is a lie, and a bar that sits
still looks like a hang. After a while without progress (ten seconds, and five times what a
unit took so far), the bar says how long nothing has happened instead. A slow step that is
normal for the work is not called a stall.

## A clock that keeps ticking

A bar that is not redrawn while one slow item runs looks frozen, and a frozen bar looks like
a crash. On a terminal a thread redraws the bar ten times a second; in a notebook the widget
keeps time in the browser. The fill only moves when work is done: it never runs ahead of
the work.

## Motion that makes waiting feel shorter

Studies by Harrison and colleagues found that a bar feels faster when it has faint ribbing
that moves backwards, against the direction of progress, and when it does not slow down
near the end. The notebook widget's running bar has such ribbing; it stops when the work
does, and for anyone who asked their system to reduce motion.

## Ending in words

A bar that just stops leaves you to guess what happened. Every bar ends as done, failed (and
why) or stopped, and says so in words as well as in colour, because colour alone is lost on
some readers, in some logs, and in a notebook read as text.
