"""
Tests for `jlx run`.

These start real kernels, so the notebooks are kept to a couple of cells. Run
with:

    pytest tests/test_cli_run.py
"""

import base64
import json
import os

import pytest

from jupyter_lab_extractor.cli import NB_PATH_ENV_VAR, RunError, discover, main, run_one

nbformat = pytest.importorskip("nbformat")
pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")


def _notebook(*sources):
    """A minimal notebook whose code cells hold `sources`."""
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(src) for src in sources]
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    return nb


def _write_notebook(path, *sources):
    nbformat.write(_notebook(*sources), str(path))
    return path


def _outputs(path):
    nb = nbformat.read(str(path), as_version=4)
    return [cell.get("outputs", []) for cell in nb.cells]


def _first_mime(cell, mime):
    """The `mime` payload of a raw-JSON cell's first output carrying it.

    nbformat splits text payloads into a list of lines on write but leaves
    base64 blobs as one string, so both shapes have to be handled.
    """
    for out in cell.get("outputs", []):
        data = out.get("data", {})
        if mime in data:
            value = data[mime]
            return "".join(value) if isinstance(value, list) else value
    return None


@pytest.fixture(autouse=True)
def _clear_nb_path_env():
    """run_one sets this in the process env; don't leak it between tests."""
    yield
    os.environ.pop(NB_PATH_ENV_VAR, None)


# --- discover ---------------------------------------------------------------

def test_discover_passes_through_explicit_files(tmp_path):
    nb = _write_notebook(tmp_path / "a.ipynb", "x = 1")
    assert [str(p) for p in discover([str(nb)])] == [str(nb)]


def test_discover_walks_directories(tmp_path):
    _write_notebook(tmp_path / "a.ipynb", "x = 1")
    (tmp_path / "sub").mkdir()
    _write_notebook(tmp_path / "sub" / "b.ipynb", "x = 2")

    found = sorted(p.name for p in discover([str(tmp_path)]))

    assert found == ["a.ipynb", "b.ipynb"]


def test_discover_skips_checkpoints(tmp_path):
    _write_notebook(tmp_path / "a.ipynb", "x = 1")
    checkpoints = tmp_path / ".ipynb_checkpoints"
    checkpoints.mkdir()
    _write_notebook(checkpoints / "a-checkpoint.ipynb", "x = 1")

    found = [p.name for p in discover([str(tmp_path)])]

    assert found == ["a.ipynb"]


# --- executing --------------------------------------------------------------

def test_run_writes_outputs_back_in_place(tmp_path):
    nb_path = _write_notebook(tmp_path / "nb.ipynb", "print('hello')")

    assert run_one(nb_path) is True

    outputs = _outputs(nb_path)[0]
    assert any("hello" in out.get("text", "") for out in outputs)


def test_check_mode_executes_without_writing(tmp_path):
    nb_path = _write_notebook(tmp_path / "nb.ipynb", "print('hello')")
    before = nb_path.read_bytes()

    assert run_one(nb_path, in_place=False) is True

    assert nb_path.read_bytes() == before


def test_relative_paths_resolve_against_the_notebooks_own_folder(tmp_path, monkeypatch):
    """The kernel cwd must be the notebook's directory, not the invocation cwd."""
    nb_dir = tmp_path / "nested"
    nb_dir.mkdir()
    nb_path = _write_notebook(nb_dir / "nb.ipynb", "open('side_effect.txt', 'w').write('x')")

    monkeypatch.chdir(tmp_path)
    assert run_one(nb_path) is True

    assert (nb_dir / "side_effect.txt").exists()
    assert not (tmp_path / "side_effect.txt").exists()


# --- failures ---------------------------------------------------------------

def test_failing_cell_stops_the_run_and_saves_the_traceback(tmp_path):
    nb_path = _write_notebook(tmp_path / "nb.ipynb", "1 / 0", "print('later')")

    assert run_one(nb_path) is False

    cells = _outputs(nb_path)
    assert any(out["output_type"] == "error" for out in cells[0])
    # Execution stopped: the cell after the failure never ran.
    assert cells[1] == []


def test_allow_errors_continues_but_still_reports_failure(tmp_path):
    nb_path = _write_notebook(tmp_path / "nb.ipynb", "1 / 0", "print('later')")

    assert run_one(nb_path, allow_errors=True) is False

    cells = _outputs(nb_path)
    assert any(out["output_type"] == "error" for out in cells[0])
    assert any("later" in out.get("text", "") for out in cells[1])


def test_run_stops_at_the_failure_leaving_a_later_healthy_cell_unrun(tmp_path):
    """A good prefix, a raising cell, then a good cell that must not execute.

    The two-cell case above shows the traceback is kept; this one shows the
    stop is a real stop -- a perfectly runnable cell downstream of the failure
    is left alone rather than run out of a broken state.
    """
    nb_path = _write_notebook(
        tmp_path / "nb.ipynb",
        "a = 1",
        "b = a + 1",
        "print('checkpoint', b)",
        "raise ValueError('boom')",
        "print('never runs')",
    )

    assert run_one(nb_path) is False

    cells = _outputs(nb_path)
    # The kosher prefix ran.
    assert cells[0] == []
    assert cells[1] == []
    assert any("checkpoint 2" in out.get("text", "") for out in cells[2])
    # The fourth cell is where it stopped.
    errors = [out for out in cells[3] if out["output_type"] == "error"]
    assert [err["ename"] for err in errors] == ["ValueError"]
    # And nothing past it ran, even though it would have succeeded.
    assert cells[4] == []


def test_run_one_rejects_a_missing_notebook(tmp_path):
    with pytest.raises(RunError):
        run_one(tmp_path / "nope.ipynb")


def test_run_errors_when_no_notebooks_are_found(tmp_path, capsys):
    assert main(["run", str(tmp_path)]) == 1
    assert "No notebooks found" in capsys.readouterr().err


# --- the %%extract integration ----------------------------------------------

EXTRACT_CELL = """\
%%extract out.py
VALUE = 1
"""


def test_extract_fires_and_names_the_source_notebook(tmp_path, monkeypatch):
    """The point of the runner: extraction works headlessly with a real header.

    Without the notebook path reaching the kernel, ipynbname has no Jupyter
    server to ask and the header would read "unknown_path".
    """
    nb_path = _write_notebook(
        tmp_path / "analysis.ipynb",
        "%load_ext jupyter_lab_extractor",
        EXTRACT_CELL,
    )

    # The kernel is a separate process; make sure it can import the package
    # even from an uninstalled source checkout.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    existing = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH", repo_root + (os.pathsep + existing if existing else "")
    )

    monkeypatch.chdir(tmp_path)
    assert run_one(nb_path) is True

    extracted = (tmp_path / "out.py").read_text(encoding="utf-8")
    header = extracted.splitlines()[0]
    assert header.startswith("# Source: analysis.ipynb |")
    assert "unknown_path" not in extracted
    # The magic line itself is stripped; the cell body is kept.
    assert "VALUE = 1" in extracted
    assert "%%extract" not in extracted


# --- CLI entry point --------------------------------------------------------

def test_main_returns_zero_when_every_notebook_passes(tmp_path, capsys):
    _write_notebook(tmp_path / "a.ipynb", "x = 1")
    _write_notebook(tmp_path / "b.ipynb", "x = 2")

    assert main(["run", str(tmp_path)]) == 0

    assert "2 passed, 0 failed" in capsys.readouterr().out


def test_main_returns_one_when_a_notebook_fails(tmp_path, capsys):
    _write_notebook(tmp_path / "bad.ipynb", "1 / 0")

    assert main(["run", str(tmp_path)]) == 1

    captured = capsys.readouterr()
    assert "FAIL" in captured.err
    assert "1 failed" in captured.out


# --- rich outputs -----------------------------------------------------------

PLOT_CELL = """\
%matplotlib inline
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(0, 2 * np.pi, 200)
plt.plot(x, np.sin(x))
plt.title("sine wave")
plt.show()
"""

FRAME_CELL = """\
import pandas as pd

df = pd.DataFrame({"x": [0, 1, 2], "sin_x": [0.0, 0.841, 0.909]})
df
"""


def test_run_saves_a_figure_and_a_dataframe_into_the_notebook_json(tmp_path):
    """Rendered artifacts survive a headless run, so the .ipynb still shows them.

    nbclient only captures what the kernel emits; a plot drawn under the wrong
    backend, or a frame that never reaches the display hook, would leave a
    notebook that opens blank. The assertions read the raw JSON rather than
    going through nbformat, because what matters is the bytes on disk.
    """
    pytest.importorskip("matplotlib")
    pytest.importorskip("pandas")

    nb_path = _write_notebook(tmp_path / "plots.ipynb", PLOT_CELL, FRAME_CELL)

    assert run_one(nb_path) is True

    with open(nb_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    plot_cell, frame_cell = raw["cells"]

    png = _first_mime(plot_cell, "image/png")
    assert png is not None, "the figure produced no image/png output"
    # Decodes, and is genuinely a PNG rather than an error placeholder.
    assert base64.b64decode(png).startswith(b"\x89PNG\r\n\x1a\n")

    html = _first_mime(frame_cell, "text/html")
    assert html is not None, "the DataFrame produced no text/html output"
    assert "<table" in html
    assert "sin_x" in html
    # The plain-text repr rides along and carries the actual values.
    assert "0.841" in _first_mime(frame_cell, "text/plain")
