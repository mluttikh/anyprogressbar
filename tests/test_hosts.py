"""The notebook renderer in the real hosts: a Jupyter kernel (through nbclient) and marimo.

These start a kernel and a marimo run, so they take a few seconds.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

CELLS = [
    "import time\nfrom anyprogressbar import progress",
    (
        "for epoch in progress(range(2), 'Epochs'):\n"
        "    for _ in progress(range(6), f'Batches {epoch}'):\n"
        "        time.sleep(0.12)"
    ),
    "for _ in progress(range(5), 'Quick'):\n    pass",
    (
        "with progress(total=10, desc='Import') as bar:\n"
        "    bar.update(4)\n"
        "    raise ValueError('bad row')"
    ),
]


@pytest.fixture(scope="module")
def executed() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source) for source in CELLS])
    client = NotebookClient(nb, timeout=60, kernel_name="python3", allow_errors=True)
    client.execute()
    return nb


def displays(cell: nbformat.NotebookNode) -> list[nbformat.NotebookNode]:
    return [o for o in cell.outputs if o.output_type == "display_data"]


def test_in_a_kernel_a_tree_is_one_output_that_ends_as_html_and_text(executed):
    (output,) = displays(executed.cells[1])
    assert sorted(output.data) == ["text/html", "text/plain"]
    assert output.data["text/plain"].startswith("Epochs 100%")
    assert "2/2 · done in 00:01" in output.data["text/plain"]
    assert 'role="progressbar" aria-label="Epochs"' in output.data["text/html"]
    assert "Batches" not in output.data["text/html"]  # the children were done and went
    assert not [o for o in executed.cells[1].outputs if o.output_type == "stream"]


def test_in_a_kernel_quick_work_leaves_no_output(executed):
    assert executed.cells[2].outputs == []


def test_in_a_kernel_a_failure_is_kept_with_its_reason(executed):
    cell = executed.cells[3]
    (output,) = displays(cell)
    assert "4/10 · failed after 00:00: ValueError: bad row" in output.data["text/plain"]
    assert [o.ename for o in cell.outputs if o.output_type == "error"] == ["ValueError"]


def test_in_marimo_the_bar_is_the_cells_output(tmp_path: Path):
    app = tmp_path / "app.py"
    app.write_text(
        "import marimo\n"
        "app = marimo.App()\n\n"
        "@app.cell\n"
        "def _():\n"
        "    import time\n"
        "    from anyprogressbar import progress\n"
        "    for _ in progress(range(8), 'In marimo'):\n"
        "        time.sleep(0.1)\n"
        "    return\n",
        encoding="utf-8",
    )
    page = tmp_path / "app.html"
    run = subprocess.run(
        [sys.executable, "-m", "marimo", "export", "html", str(app), "-o", str(page)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    markup = page.read_text(encoding="utf-8")
    assert "In marimo" in markup
    assert "8/8 \\u00b7 done in 00:00" in markup or "8/8 · done in 00:00" in markup
    assert "In marimo:" not in run.stderr  # no log lines beside it
