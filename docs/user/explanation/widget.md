# How the notebook bar keeps time

## The clock is in the browser

A notebook bar only learns something when the loop reports, and during a slow step the
loop says nothing. The widget is sent the bar's numbers when they change, at most ten times
a second, and between two of those the page moves the clocks on by itself: every quarter
second it adds the time since the last report to the elapsed time, counts down the time
remaining, and says when nothing has come for long enough. The fill does not move: only the
kernel knows how much is done.

So the kernel needs no thread of its own for the bar, and the bar never looks frozen.

## What the notebook keeps

A widget in a saved notebook shows only where its state was saved too, and then only as it
was. So while the work runs the output holds the widget and, beside it, the same bar as
plain HTML and as text. When the work ends, the output is replaced by the HTML and text
alone, and the widget is closed.

A saved notebook then shows how each piece of work ended in any viewer: on GitHub, in
nbconvert's HTML, as text in a terminal. And the kernel keeps no widget for every bar that
ever ran.

## When the page shows no widgets

The page draws widgets only if anywidget's browser side is installed where Jupyter runs,
which need not be where the kernel runs. A kernel is not told how its output is drawn, so
the bar finds out:

- Each widget tells the kernel when the page has drawn it. That answer is certain, but the
  kernel reads it only once the cells that are running have ended.
- Until then, it goes by whether anywidget's browser side is installed in the kernel's own
  environment. Where it is not, a bar is a widget for half a second and plain HTML after
  that.
- If a widget was shown, and the kernel has been idle with no answer, the page shows no
  widgets: bars are plain HTML from then on, and the first says why.

Plain HTML in a page that shows no widgets is replaced in place, so it still moves; it only
stands still during a slow step.

## The same words in two languages

The text beside a bar is made in Python (terminal, log, HTML) and, between reports, in the
widget's JavaScript. Both are checked against the same list of cases, made by Python, so
that a bar does not change its wording when the widget takes over.
