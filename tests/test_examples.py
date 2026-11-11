"""The example notebooks run from start to end in a real kernel, without an error.

They sleep to have something to show, so this takes about half a minute; they run side by
side to keep it at that.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.ipynb"))


def run(path: Path) -> nbformat.NotebookNode:
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, timeout=120, kernel_name="python3").execute()
    return nb


@pytest.fixture(scope="module")
def executed() -> dict[str, nbformat.NotebookNode]:
    with ThreadPoolExecutor(len(EXAMPLES)) as pool:
        return dict(zip([p.name for p in EXAMPLES], pool.map(run, EXAMPLES), strict=True))


def texts(nb: nbformat.NotebookNode) -> list[str]:
    return [
        output.data["text/plain"]
        for cell in nb.cells
        if cell.cell_type == "code"
        for output in cell.outputs
        if output.output_type == "display_data"
    ]


def test_there_are_examples_and_they_are_committed_without_outputs():
    assert len(EXAMPLES) >= 4
    for path in EXAMPLES:
        nb = nbformat.read(path, as_version=4)
        assert not any(c.get("outputs") for c in nb.cells if c.cell_type == "code"), path.name


def test_getting_started_leaves_a_record_per_bar_and_none_for_quick_work(executed):
    records = texts(executed["getting_started.ipynb"])
    assert [r.split()[0] for r in records] == [
        "Loading", "Downloading", "Training", "Scanning", "Scanning",
    ]  # fmt: skip
    assert all("done in" in r for r in records)


def test_nested_bars_keep_the_children_that_were_asked_to_stay(executed):
    records = texts(executed["nested_bars.ipynb"])
    assert len(records) == 5
    assert records[1].count("\n") == 3  # the three datasets under their parent
    assert "alpha" not in records[4]


def test_endings_are_said_in_words(executed):
    records = texts(executed["endings_and_stalls.ipynb"])
    assert "ValueError: row 7 has no date" in records[0]
    assert "6/10 · failed after" in records[0]
    assert "2/5 · failed after" in records[1]
    assert records[1].endswith(": the server said no")
    assert "stopped after" in records[2]
    assert "6/6 · done in 00:1" in records[3]


def test_where_bars_show_writes_log_lines_and_milestones(executed):
    nb = executed["where_bars_show.ipynb"]
    printed = "".join(
        o.text for c in nb.cells if c.cell_type == "code" for o in c.outputs
        if o.output_type == "stream"
    )  # fmt: skip
    assert "Nightly import: done, 40 files in 00:0" in printed
    assert "Only this one: done" in printed
    assert "30 checked" in printed
    assert "Milestones: 50% after" in printed
    assert "Milestones: done (40 of 40)" in printed
    assert "Silent" not in printed + "".join(texts(nb))
