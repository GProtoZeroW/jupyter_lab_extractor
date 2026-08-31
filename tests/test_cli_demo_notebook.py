"""
Tests driving `tests/demo_plots.ipynb`, the checked-in demo notebook.

Where test_cli_run.py builds throwaway notebooks in tmp_path, these exercise a
real notebook a person can open: matplotlib and pandas produce genuine rich
outputs, and two `%%extract` cells stack into an importable module. That makes
it the end-to-end case for `jlx` -- pairing, headless execution, output capture
and extraction all on one file.

Run with:

    pytest tests/test_cli_demo_notebook.py
"""

import base64
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from jupyter_lab_extractor.cli import NB_PATH_ENV_VAR, counterpart, is_paired, run_one

pytest.importorskip("nbformat")
pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")
pytest.importorskip("jupytext")
pytest.importorskip("matplotlib")
pytest.importorskip("pandas")

DEMO_NOTEBOOK = Path(__file__).parent / "demo_plots.ipynb"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _first_mime(cell, mime):
    """The `mime` payload of a raw-JSON cell's first output carrying it."""
    for out in cell.get("outputs", []):
        data = out.get("data", {})
        if mime in data:
            value = data[mime]
            return "".join(value) if isinstance(value, list) else value
    return None


def _any_mime(cells, mime):
    """The first `mime` payload found anywhere in `cells`.

    Located by content rather than cell index so that editing the demo notebook
    doesn't quietly turn these into assertions about the wrong cell.
    """
    for cell in cells:
        found = _first_mime(cell, mime)
        if found is not None:
            return found
    return None


@pytest.fixture(autouse=True)
def _clear_nb_path_env():
    """run_one sets this in the process env; don't leak it between tests."""
    yield
    os.environ.pop(NB_PATH_ENV_VAR, None)


@pytest.fixture(scope="module")
def executed_demo(tmp_path_factory):
    """The demo notebook, copied out of the repo and run once by `jlx run`.

    Copied because the run rewrites the notebook and drops extracted files
    beside it; the repo's own copy is regenerated deliberately, not as a side
    effect of the test suite.
    """
    workdir = tmp_path_factory.mktemp("demo")
    nb_path = workdir / DEMO_NOTEBOOK.name
    shutil.copy(DEMO_NOTEBOOK, nb_path)

    # The kernel is a separate process; let it import the package from the
    # source checkout even when it isn't installed.
    env_before = os.environ.get("PYTHONPATH")
    existing = env_before or ""
    os.environ["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
    cwd_before = os.getcwd()
    os.chdir(workdir)
    try:
        ok = run_one(nb_path)
    finally:
        os.chdir(cwd_before)
        if env_before is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = env_before

    assert ok is True, "the demo notebook must run clean"
    return workdir, nb_path


# --- the notebook as shipped ------------------------------------------------

def test_the_demo_notebook_is_paired_with_a_py_twin():
    """`jlx pair` has been run on it, and the twin is actually on disk.

    Metadata alone isn't enough: a notebook can carry jupytext formats while
    its counterpart is missing, which is exactly the state that makes the
    pairing useless for diffing.
    """
    assert is_paired(DEMO_NOTEBOOK) is True
    twin = Path(counterpart(str(DEMO_NOTEBOOK)))
    assert twin.suffix == ".py"
    assert twin.exists(), f"{twin.name} is missing; run `jlx pair {DEMO_NOTEBOOK}`"


# --- rich outputs survive a headless run ------------------------------------

def test_run_embeds_the_matplotlib_figure(executed_demo):
    _, nb_path = executed_demo
    cells = json.loads(nb_path.read_text(encoding="utf-8"))["cells"]

    png = _any_mime(cells, "image/png")

    assert png is not None, "no figure was captured from the plotting cell"
    assert base64.b64decode(png).startswith(b"\x89PNG\r\n\x1a\n")


def test_run_embeds_the_pandas_dataframe(executed_demo):
    _, nb_path = executed_demo
    cells = json.loads(nb_path.read_text(encoding="utf-8"))["cells"]

    html = _any_mime(cells, "text/html")

    assert html is not None, "no rendered table was captured from the frame cell"
    assert "<table" in html
    assert "sin_x" in html


# --- extraction fires during that same run ----------------------------------

def test_run_extracts_both_cells_into_one_module(executed_demo):
    workdir, _ = executed_demo
    extracted = (workdir / "demo_outputs" / "analysis.py").read_text(encoding="utf-8")

    # -w then -a: two blocks, each with its own provenance header.
    assert extracted.count("# Source:") == 2
    assert "demo_plots.ipynb" in extracted
    assert "unknown_path" not in extracted
    assert "def sine_wave" in extracted
    assert "def sine_table" in extracted
    # Magic lines mean nothing in a .py file and must not survive.
    assert "%matplotlib" not in extracted
    assert "%%extract" not in extracted


def test_the_extracted_module_is_importable_and_works(executed_demo):
    """The point of extracting: what lands on disk is real, runnable code."""
    workdir, _ = executed_demo
    module_path = workdir / "demo_outputs" / "analysis.py"

    spec = importlib.util.spec_from_file_location("demo_analysis", module_path)
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)

    x, y = analysis.sine_wave(cycles=2, points=64)
    assert len(x) == len(y) == 64

    frame = analysis.sine_table(points=5)
    assert list(frame.columns) == ["x", "sin_x"]
    assert len(frame) == 5
    # sin(0) == 0 anchors the first row; a garbled export would not land here.
    assert frame["sin_x"].iloc[0] == pytest.approx(0.0)
