"""
Tests for `jlx pair`.

Plain pytest -- no kernel or notebook server needed, since pairing is pure
file manipulation. Run with:

    pytest tests/test_cli_pair.py
"""

import json
import os

import pytest

from jupyter_lab_extractor.cli import PAIRED_FORMATS, PairError, counterpart, main, pair

jupytext = pytest.importorskip("jupytext")


PY_SOURCE = """\
# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
x = 42
"""


def _formats(path):
    """The jupytext formats metadata recorded in a file, or None."""
    return jupytext.read(path).metadata.get("jupytext", {}).get("formats")


def _write_py(path, paired=False):
    path.write_text(PY_SOURCE, encoding="utf-8")
    if paired:
        nb = jupytext.read(str(path))
        nb.metadata.setdefault("jupytext", {})["formats"] = PAIRED_FORMATS
        jupytext.write(nb, str(path), fmt="py:percent")
    return path


def _write_ipynb(path, paired=False):
    nb = jupytext.reads(PY_SOURCE, fmt="py:percent")
    if paired:
        nb.metadata.setdefault("jupytext", {})["formats"] = PAIRED_FORMATS
    jupytext.write(nb, str(path))
    return path


# --- counterpart ------------------------------------------------------------

def test_counterpart_maps_both_directions():
    assert counterpart("a/b/nb.ipynb") == "a/b/nb.py"
    assert counterpart("a/b/nb.py") == "a/b/nb.ipynb"


def test_counterpart_rejects_other_extensions():
    with pytest.raises(PairError):
        counterpart("notes.md")


# --- pairing from one existing half -----------------------------------------

def test_pair_from_py_creates_ipynb(tmp_path):
    src = _write_py(tmp_path / "nb.py")
    target = tmp_path / "nb.ipynb"

    pair(str(src))

    assert target.exists()
    assert _formats(str(target)) == PAIRED_FORMATS
    assert _formats(str(src)) == PAIRED_FORMATS
    # Content survived the round trip.
    assert "x = 42" in src.read_text(encoding="utf-8")
    assert "x = 42" in json.dumps(json.loads(target.read_text(encoding="utf-8")))


def test_pair_from_ipynb_creates_py(tmp_path):
    src = _write_ipynb(tmp_path / "nb.ipynb")
    target = tmp_path / "nb.py"

    pair(str(src))

    assert target.exists()
    assert _formats(str(target)) == PAIRED_FORMATS
    assert _formats(str(src)) == PAIRED_FORMATS
    assert "x = 42" in target.read_text(encoding="utf-8")


def test_pair_from_headerless_py_records_formats_on_both_sides(tmp_path):
    """A .py with no YAML header must still end up genuinely paired.

    Jupytext reads such a file with notebook_metadata_filter="-all", which
    would suppress the formats metadata on the text side.
    """
    src = tmp_path / "nb.py"
    src.write_text("# %%\nx = 42\n", encoding="utf-8")

    pair(str(src))

    assert _formats(str(src)) == PAIRED_FORMATS
    assert _formats(str(tmp_path / "nb.ipynb")) == PAIRED_FORMATS


def test_pair_is_idempotent(tmp_path):
    """Pairing twice must not turn into the both-halves-unpaired refusal."""
    src = tmp_path / "nb.py"
    src.write_text("# %%\nx = 42\n", encoding="utf-8")

    pair(str(src))
    after_first = (src.read_bytes(), (tmp_path / "nb.ipynb").read_bytes())

    assert "Already paired" in pair(str(src))
    assert (src.read_bytes(), (tmp_path / "nb.ipynb").read_bytes()) == after_first


def test_pair_carries_kernelspec_into_generated_ipynb(tmp_path):
    src = _write_py(tmp_path / "nb.py")

    pair(str(src))

    nb = jupytext.read(str(tmp_path / "nb.ipynb"))
    assert nb.metadata["kernelspec"]["name"] == "python3"


# --- already paired ---------------------------------------------------------

def test_pair_is_a_noop_when_already_paired(tmp_path):
    src = _write_py(tmp_path / "nb.py", paired=True)
    other = _write_ipynb(tmp_path / "nb.ipynb", paired=True)
    before = (src.read_bytes(), other.read_bytes())

    message = pair(str(src))

    assert "Already paired" in message
    assert (src.read_bytes(), other.read_bytes()) == before


def test_pair_is_a_noop_on_the_projects_own_test_notebook():
    """tests/test_extract_magic.ipynb is already paired; jlx must not touch it."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    nb_path = os.path.join(repo_root, "tests", "test_extract_magic.ipynb")
    py_path = os.path.join(repo_root, "tests", "test_extract_magic.py")
    before = (open(nb_path, "rb").read(), open(py_path, "rb").read())

    message = pair(nb_path)

    assert "Already paired" in message
    assert (open(nb_path, "rb").read(), open(py_path, "rb").read()) == before


# --- refusal cases ----------------------------------------------------------

def test_pair_refuses_when_both_halves_exist_unpaired(tmp_path):
    src = _write_py(tmp_path / "nb.py")
    other = _write_ipynb(tmp_path / "nb.ipynb")
    before = (src.read_bytes(), other.read_bytes())

    with pytest.raises(PairError) as excinfo:
        pair(str(src))

    assert "not paired" in str(excinfo.value)
    # Neither side may be modified when we refuse.
    assert (src.read_bytes(), other.read_bytes()) == before


def test_pair_rejects_a_missing_file(tmp_path):
    with pytest.raises(PairError):
        pair(str(tmp_path / "nope.ipynb"))


def test_pair_rejects_an_unsupported_extension(tmp_path):
    stray = tmp_path / "notes.md"
    stray.write_text("hello\n", encoding="utf-8")
    with pytest.raises(PairError):
        pair(str(stray))


# --- CLI entry point --------------------------------------------------------

def test_main_returns_zero_on_success(tmp_path, capsys):
    src = _write_py(tmp_path / "nb.py")

    assert main(["pair", str(src)]) == 0

    assert (tmp_path / "nb.ipynb").exists()
    assert "Paired" in capsys.readouterr().out


def test_main_returns_one_and_explains_on_refusal(tmp_path, capsys):
    src = _write_py(tmp_path / "nb.py")
    _write_ipynb(tmp_path / "nb.ipynb")

    assert main(["pair", str(src)]) == 1

    captured = capsys.readouterr()
    assert "jlx:" in captured.err
    assert "jupytext --set-formats" in captured.err
