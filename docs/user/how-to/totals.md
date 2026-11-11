# Totals, units and positions

```python exec="on" session="totals"
import time
from anyprogressbar import progress
from docs_pictures import fake, show_html  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide
```

## Where the total comes from

When you wrap something with a length (a list, a `range`, a dict, a DataFrame), its length
is the total:

```python
for path in progress(paths, "Copying", unit="files"):
    ...
```

A generator has no length. Pass the total if you know it:

```python
for row in progress(read_rows(path), "Reading", total=row_count, unit="rows"):
    ...
```

## Work of unknown size

Without a total, the bar claims no percentage: a block runs along the track, and the count,
the elapsed time and the rate say how the work goes.

```python exec="on" source="above" html="true" session="totals"
def rows():
    for i in range(50):
        time.sleep(0.05)
        yield i

for row in progress(rows(), "Scanning", unit="rows"):
    pass
print(show_html(at=1.5))  # markdown-exec: hide
```

## A total that is known later, or changes

Set it when you know it, with `set(total=...)`. The bar turns from a running block into a
filling bar:

```python
with progress(desc="Crawling", unit="pages") as bar:
    for page in crawl(start):
        bar.update()
        bar.set(total=len(queue) + bar.n)  # the queue grows as pages are found
```

## Work that reports where it is

Some work tells you its position, not how far it moved since last time: a download's bytes
so far, a file's offset, a solver's iteration. Use `set(n)`:

```python
with progress(total=size, desc="Downloading", unit="B") as bar:
    for received in download(url):   # bytes received so far
        bar.set(received)
```

## Units

`unit` is the word after the count and in the rate: `"it"` by default, then whatever is
counted (`"files"`, `"rows"`, `"MB"`, `"batches"`). The count is shown as it is: pass
megabytes as megabytes. Counts that are not whole are shown with three significant digits.

```python exec="on" source="above" html="true" session="totals"
sizes = [1.5, 0.25, 3.0, 0.75]

with progress(total=sum(sizes), desc="Uploading", unit="GB") as bar:
    for size in sizes:
        time.sleep(size)
        bar.update(size)
print(show_html())  # markdown-exec: hide
```
