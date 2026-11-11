# Bars inside bars, and threads

```python exec="on" session="nested"
import time
from anyprogressbar import progress
from docs_pictures import fake, show_html  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide
```

## Children

A bar that is made while another one runs (inside its `for` loop or its `with` block)
becomes its child. Children are drawn under their parent, indented, in the same output.
That holds across function calls: a function with a bar, called from a loop with a bar,
shows its bar under the loop's ([tutorial](../tutorials/functions.md)).

## Which children stay

A child that is done goes from the picture; one that failed or stopped stays, with its
reason. To keep children that are done, pass `leave=True`. To have a bar of its own go
when done, pass `leave=False`:

```python
for name in progress(datasets, "Datasets"):
    for row in progress(load(name), name, leave=True):   # keep each dataset's line
        ...
```

## The parent's time remaining

A parent's time remaining counts the part of its running children that is done. By default
a child counts as one unit of its parent, which is right for the inner loop of a nested
loop. When a child covers more or less, give its `weight`: how many of the parent's units
it covers.

Here the parent counts megabytes, and each file's bar counts its pages:

```python exec="on" source="above" html="true" session="nested"
files = {"a.pdf": 40, "b.pdf": 10, "c.pdf": 30}  # sizes in MB

with progress(total=sum(files.values()), desc="Converting", unit="MB") as overall:
    for name, size in files.items():
        with progress(total=20, desc=name, unit="pages", weight=size) as pages:
            for page in range(20):
                time.sleep(size / 200)
                pages.update()
        overall.update(size)
print(show_html(at=3.0))  # markdown-exec: hide
```

Two bars one after the other inside one unit of a parent should each get a `weight` that
says their share (for example `0.5` each); without it the parent counts each as a whole
unit and its estimate is too hopeful while they run.

## Work in other threads

A thread does not know which bar is running in the thread that started it. Say so with
`parent=`:

```python
from concurrent.futures import ThreadPoolExecutor

def fetch(site, parent):
    with progress(total=10, desc=site, unit="pages", parent=parent) as bar:
        for page in range(10):
            ...
            bar.update()
    parent.update()

with progress(total=len(sites), desc="Sites") as overall, ThreadPoolExecutor(4) as pool:
    for site in sites:
        pool.submit(fetch, site, overall)
```

Bars may be updated from any thread. Bars in other processes are not supported yet: report
back to the main process and update the bar there.
