# Show values beside the bar

```python exec="on" session="values"
import time
from anyprogressbar import progress
from docs_pictures import fake, show_html  # markdown-exec: hide
progress, time = fake(progress)  # markdown-exec: hide
```

## Metrics

`set_postfix` puts `name=value` pairs after the numbers. Each call replaces all of the last
ones. Floats are shown with three significant digits; anything else as it prints.

```python exec="on" source="above" html="true" session="values"
with progress(total=30, desc="Training", unit="steps") as bar:
    for step in range(30):
        time.sleep(0.1)
        bar.update()
        bar.set_postfix(loss=2 / (step + 2), acc=step / 30, best_epoch=step // 10)
print(show_html())  # markdown-exec: hide
```

Call it as often as you like: it only stores the values; the bar is drawn a few times a
second at most.

## What is being worked on

`set_description` changes the bar's name, for example to the item at hand:

```python exec="on" source="above" html="true" session="values"
files = ["2024.csv", "2025.csv", "2026.csv"]

with progress(total=len(files), desc="Loading", unit="files") as bar:
    for name in files:
        bar.set_description(f"Loading {name}")
        time.sleep(1)
        bar.update()
    bar.set_description("Loaded")
print(show_html())  # markdown-exec: hide
```

A name that changes many times a second is hard to read. For many small items, show a
count of something instead, with `set_postfix`.
