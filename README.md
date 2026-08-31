# jupyter_lab_extractor

`jupyter_lab_extractor` is a Jupyter cell magic (plus a few utility tools) that
extracts a notebook's cell contents to a designated Python file, cell by cell,
without breaking your notebook's normal usability.

## The Problem

Jupyter does ship with a built-in `%%writefile` magic, but it has a fundamental
flaw: it writes the cell to a file instead of running it, so your notebook stops
being executable from top to bottom.

That's the issue `jupyter_lab_extractor`'s `%%extract` solves:

**No compromise between a cell being executable and its contents being extracted
to a file.**

The second issue, and this one is a personal preference of the user, is the
separation of code and docs. In a notebook, code and docs live as one. This gives
you a clean way to get the code back out to `/src`, or wherever you need it for
normal execution, while keeping the source entangled with docs that too often
never get written or drift away from the code they describe.

**Note:** Tools like [Jupytext](https://github.com/mwouts/jupytext) solve part of
this problem. Jupytext is a great tool, and `jupyter_lab_extractor` uses it in its
own utility tools, but its goal is to sync an entire notebook to a script file.
That's useful for plenty of reasons, but it's all-or-nothing. You don't get to
pick where each cell's contents are written.

## What the Magic Does

`%%extract` writes a cell's contents to a file *and* runs the cell normally.
Your notebook stays fully executable, and you get fine-grained, cell-by-cell
control over what code ends up in which file.

Each extracted block includes a metadata comment so you can trace it back to its
source. So in the notebook `notebooks/analysis.ipynb`, this cell:

```python
%%extract src/utils.py
import os
CONSTANT = 100
```

runs as it normally would, and also writes its contents to `src/utils.py`:

```python
# Source: notebooks/analysis.ipynb | Cell In[3] | 2026-02-01 14:30:22
import os
CONSTANT = 100
```

## Install

With `pip`:

```bash
pip install jupyter-lab-extractor
```

With [`uv`](https://github.com/astral-sh/uv):

```bash
uv add jupyter-lab-extractor
```

Or add it to your `pyproject.toml` by hand:

```toml
[project]
dependencies = [
    "jupyter-lab-extractor",
]
```

## Magic Usage

Load the `%%extract` magic once per notebook, preferably in the top cell:

```python
%load_ext jupyter_lab_extractor
```

> **`%%extract` always writes the file, even when the cell fails.**
>
> The export is a copy of the cell's contents, not a record of whether those
> contents worked. A cell that raises still lands in the target file, so a
> broken cell gives you a broken file rather than a silently stale one. Judge
> whether a cell ran clean from the notebook output or from `jlx run`'s exit
> status, never from the fact that the file was written.

### Write to a new file (default: overwrite)

```python
%%extract utils.py
import os

def get_data_path():
    return os.path.join("data", "raw")
```

The cell runs normally **and** its contents, minus any magic lines, are written
to the file named in the magic argument. In this case, `utils.py`.

### Append to an existing file

```python
%%extract utils.py -a
def process_data(path):
    # ...
    pass
```

Use `-a` to add to a file across multiple cells. This lets you build a module up
piece by piece as you develop in the notebook, concatenating each cell's contents
in the order the cells run.

### Overwrite explicitly

```python
%%extract utils.py -w
# Fresh start: replaces everything in utils.py
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

`%%extract` plays nicely with other cell magics. You can extract a cell to a file
and run it as a test in the same cell:

```python
%%extract tests/test_utils.py -a
%%ipytest

def test_get_data_path():
    result = get_data_path()
    assert "data" in result
```

The cell is extracted, with `%%ipytest` stripped from the output file, and ipytest
runs the test, all in one go. This means your test notebook is both the test runner
and the source of truth for the exported test file. See
`tests/test_extract_magic.ipynb` for a working example of this pattern.

### Stack ipytest cells into one clean file (`--strip-ipytest`)

The other common ipytest workflow calls `ipytest.clean()` and `ipytest.run()`
explicitly, once per cell:

```python
%%extract tests/test_clkgen.py -a --strip-ipytest
ipytest.clean()


def test_encode_round_trips_exactly(unbounded):
    unbounded.requested_value = 1.234567891e9
    assert float(unbounded.requested_value_scpi) == 1.234567891e9


ipytest.run()
```

Those calls drive the *in-notebook* runner. Written verbatim into a `.py` file
they'd wipe or re-run the collected tests at import time, and repeating them once
per cell would leave the stacked file full of scaffolding.

`--strip-ipytest` drops those calls: `ipytest.clean()`, `ipytest.clean_tests()`,
`ipytest.run()` (with or without arguments), and `ipytest.autoconfig()`, along with
the blank padding they leave behind. Put the flag on every cell, and any number of
clean/define/run cells stack via `-a` into one importable module:

```python
# Source: notebooks/clkgen.ipynb | Cell In[12] | 2026-02-01 14:30:22
def test_encode_round_trips_exactly(unbounded):
    unbounded.requested_value = 1.234567891e9
    assert float(unbounded.requested_value_scpi) == 1.234567891e9

# Source: notebooks/clkgen.ipynb | Cell In[13] | 2026-02-01 14:30:41
def test_encode_is_not_g_format(unbounded):
    unbounded.requested_value = 1.234567891e9
    assert unbounded.requested_value_scpi != f"{1.234567891e9:g}"
```

Your notebook still cleans and runs each test as you write it, and the exported
file is plain pytest. The flag is opt-in. Without it, `ipytest` calls are written
through unchanged.

## The `jlx` Command Line Tool

`%%extract` runs inside a notebook. `jlx` is the other half: it drives notebooks
from the terminal, so a notebook can run and extract its files without opening
Jupyter. That makes extraction something you can put in a CI/CD pipeline.

```bash
pip install jupyter-lab-extractor[cli]
```

### Run a notebook headlessly

```bash
jlx run notebooks/analysis.ipynb
```

Executes the notebook the way running it in the browser would: every cell runs,
`%%extract` writes its files, and cell outputs, matplotlib figures included, are
saved back into the `.ipynb`. The kernel comes from the notebook's own kernelspec,
and cells run with the notebook's directory as their working directory, so relative
paths behave exactly as they do interactively.

The first failing cell stops the run. The error is reported on stderr and the
notebook is still written, so the traceback is there in the cell when you open it:

```
FAIL  notebooks/analysis.ipynb
      An error occurred while executing the following cell:
      ...
0 passed, 1 failed
```

Pass directories to run everything under them (`.ipynb_checkpoints` is skipped):

```bash
jlx run notebooks/
```

| Flag | Effect |
|---|---|
| `--kernel NAME` | Force a kernel. Default: the notebook's own kernelspec. |
| `--timeout SECS` | Per-cell timeout. Default: 600. |
| `--allow-errors` | Keep going past failing cells. The run still exits non-zero. |
| `--check` | Execute without writing outputs back. CI mode. |

Exit status is 0 only when every notebook ran clean, so `jlx run --check notebooks/`
works as a CI gate.

### Pair a notebook with a `.py` twin

```bash
jlx pair notebooks/analysis.ipynb
```

This is a convenience runner for setting up a
[Jupytext](https://github.com/mwouts/jupytext) `ipynb,py:percent` pairing between a
`.py` and an `.ipynb`, so the notebook has a script twin that diffs cleanly in
version control. Give it either half, the `.ipynb` or the `.py`, and it creates the
other.

It is deliberately cautious:

- **Already paired?** It says so and changes nothing. Jupytext is already keeping
  the two sides in step.
- **Both halves exist but are not paired?** It refuses. Syncing either direction
  would overwrite the other side's content, so it tells you to pick the
  authoritative file and pair it yourself.

## How It Differs From Alternatives

| | Runs the cell? | Per-cell control? | Multiple output files? |
|---|---|---|---|
| `%%writefile` | No | Yes | Yes |
| Jupytext | Yes | No (whole notebook) | No (one file) |
| `%%extract` | **Yes** | **Yes** | **Yes** |

This is not a replacement for Jupytext. Jupytext is excellent for syncing notebooks
to scripts for version control and diffing. `%%extract` is for when you want to
selectively pull specific cells out into standalone Python files while keeping your
notebook runnable.

## Dependencies

- [IPython](https://ipython.org/)
- [ipynbname](https://github.com/msm1089/ipynbname): resolves the notebook name and
  path for metadata headers

## Development

```bash
git clone https://github.com/GProtoZeroW/jupyter_lab_extractor.git
cd jupyter_lab_extractor
pip install -e ".[dev]"
```

Tests live in `tests/test_extract_magic.ipynb` and use
[ipytest](https://github.com/chmp/ipytest) for in-notebook testing. Run it from the
terminal with `jlx run tests/test_extract_magic.ipynb`. The `jlx` commands themselves
are covered by plain pytest in `tests/test_cli_pair.py` and `tests/test_cli_run.py`.
Run those files by name, because a bare `pytest` at the repo root also collects the
Jupytext twin, which is not a test module.

Logging in the test cells uses the standard library `logging` module, formatted to
match loguru's output. The test notebook is paired with a `.py` percent script via
[Jupytext](https://github.com/mwouts/jupytext) for cleaner diffs in version control.
Always run from the `.ipynb`. The `.py` is for diffing only.

These are not required to use the package, only for development:

- [ipytest](https://github.com/chmp/ipytest): run pytest inside notebook cells
- [Jupytext](https://github.com/mwouts/jupytext): notebook/script pairing for
  version control
- [nbclient](https://github.com/jupyter/nbclient): headless notebook execution
  behind `jlx run`

## Credits

**Author:** [GProtoZeroW](https://github.com/GProtoZeroW)

This project was crafted with extensive help from:

- Claude Opus 4.5 (web chat)
- Claude Code (claude.ai/code) running Claude Opus 4.1

## License

MIT
