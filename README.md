# jupyter_lab_extractor

A Jupyter cell magic that extracts cell contents to Python files — without breaking your notebook.

## The Problem

Jupyter's built-in `%%writefile` has a fundamental flaw: it writes the cell to a file **instead** of running it. Your notebook stops being executable. You have to choose between a notebook that runs and a notebook that exports code. That's a bad trade.

Tools like Jupytext solve a different problem — they sync an entire notebook to a script file. That's great for version control, but it's all-or-nothing. You don't get to pick which cells go where.

## What This Does

`%%extract` writes cell contents to a file **and** runs the cell normally. Your notebook stays fully executable. You get fine-grained, cell-by-cell control over what code ends up in which file.

Each extracted block includes a metadata comment so you can trace it back to its source:

```python
# Source: notebooks/analysis.ipynb | Cell In[3] | 2026-02-01 14:30:22
import os
CONSTANT = 100
```

## Install

```bash
pip install jupyter-lab-extractor
```

## Usage

Load the magic once per notebook:

```python
%load_ext jupyter_lab_extractor
```

### Write to a new file (default: overwrite)

```python
%%extract utils.py
import os

def get_data_path():
    return os.path.join("data", "raw")
```

The cell runs normally **and** the contents (minus any magic lines) are written to `utils.py`.

### Append to an existing file

```python
%%extract utils.py -a
def process_data(path):
    # ...
    pass
```

Use `-a` to add to a file across multiple cells. Build up a module piece by piece as you develop in the notebook.

### Overwrite explicitly

```python
%%extract utils.py -w
# Fresh start — replaces everything in utils.py
```

`-w` is the default, but you can be explicit about it.

### Nested paths

Directories are created automatically:

```python
%%extract src/models/classifier.py
class Classifier:
    pass
```

### Combine with ipytest

`%%extract` plays nicely with other cell magics. You can extract a cell to a file and run it as a test in the same cell:

```python
%%extract tests/test_utils.py -a
%%ipytest

def test_get_data_path():
    result = get_data_path()
    assert "data" in result
```

The cell is extracted (with `%%ipytest` stripped from the output file), and ipytest runs the test — all in one shot. This means your test notebook is both the test runner and the source of truth for the exported test file. See `tests/test_extract_magic.ipynb` for a working example of this pattern.

## How It Differs From Alternatives

| | Runs the cell? | Per-cell control? | Multiple output files? |
|---|---|---|---|
| `%%writefile` | No | Yes | Yes |
| Jupytext | Yes | No (whole notebook) | No (one file) |
| `%%extract` | **Yes** | **Yes** | **Yes** |

This is not a replacement for Jupytext. Jupytext is excellent for syncing notebooks to scripts for version control and diffing. `%%extract` is for when you want to selectively pull specific cells out into standalone Python files while keeping your notebook runnable.

## Dependencies

- [IPython](https://ipython.org/)
- [ipynbname](https://github.com/msm1089/ipynbname) — used to resolve notebook name and path for metadata headers

## Development

```bash
git clone https://github.com/GProtoZeroW/jupyter_lab_extractor.git
cd jupyter_lab_extractor
pip install -e .
pip install ipytest jupytext loguru
```

Tests live in `tests/test_extract_magic.ipynb` and use [ipytest](https://github.com/chmp/ipytest) for in-notebook testing. The test notebook is paired with a `.py` percent script via [Jupytext](https://github.com/mwouts/jupytext) for cleaner diffs in version control — always run from the `.ipynb`, the `.py` is for diffing only.

These are not required to use the package, only for development:

- [ipytest](https://github.com/chmp/ipytest) — run pytest inside notebook cells
- [Jupytext](https://github.com/mwouts/jupytext) — notebook/script pairing for version control
- [loguru](https://github.com/Delgan/loguru) — logging in test cells

## License

MIT