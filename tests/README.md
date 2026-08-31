# Tests

Two kinds of test live here, because the package has two halves that cannot be
tested the same way.

`%%extract` is a cell magic. It needs a live IPython kernel, so it is tested
from inside a notebook with [ipytest](https://github.com/chmp/ipytest). `jlx` is
an ordinary command line tool, so it is tested with plain pytest.

## What is here

```
tests/
├── test_extract_magic.ipynb ──pair──> test_extract_magic.py   the magic, 19 in-notebook tests
│        └── writes ──> test_demo_outputs/*.py                 what those tests extracted
│
├── demo_plots.ipynb ────────pair──> demo_plots.py             the jlx demo, matplotlib + pandas
│        └── writes ──> demo_outputs/analysis.py               what the demo extracted
│
├── test_cli_pair.py            14 tests   jlx pair
├── test_cli_run.py             15 tests   jlx run, on throwaway notebooks
└── test_cli_demo_notebook.py    5 tests   jlx run, on demo_plots.ipynb
```

### The notebooks

**`test_extract_magic.ipynb`** is the source of truth for the magic. Each
`%%ipytest` cell is a pytest-style test that exercises `%%extract` against a
real kernel: writing, appending, overwriting, magic-line stripping,
`--strip-ipytest`, error handling. Running it writes `test_demo_outputs/`, which
is cleared and regenerated on every run.

**`demo_plots.ipynb`** is a demo rather than a test, and doubles as the fixture
for `test_cli_demo_notebook.py`. It is the one file where the whole `jlx` path
happens at once: matplotlib draws a sine wave and pandas renders a table, so a
headless run has real outputs to capture, while two `%%extract` cells stack into
`demo_outputs/analysis.py` during that same run.

Its plotting and display calls sit in plain cells, not in the extract cells, so
`analysis.py` stays importable with no side effects. `test_cli_demo_notebook.py`
relies on that: it imports the extracted module and calls its functions, which
is what proves the export is runnable code and not just plausible-looking text.

### The `.py` twins

`test_extract_magic.py` and `demo_plots.py` are
[Jupytext](https://github.com/mwouts/jupytext) `py:percent` mirrors, kept in
sync automatically so the notebooks diff readably in git.

**They are not runnable and not test modules.** Cell magics mean nothing outside
a kernel. Always edit and run the `.ipynb`; the `.py` is for diffing only. This
is why a bare `pytest` at the repo root fails: it tries to collect
`test_extract_magic.py`, whose name matches pytest's discovery pattern. Run the
CLI test files by name instead.

### The output directories

`test_demo_outputs/` and `demo_outputs/` hold files written by `%%extract`
during a notebook run. They are committed so you can see what extraction
actually produces, but nothing hand-edits them — they are overwritten every
time their notebook runs.

## Running them

```bash
# the jlx tests -- by name, see "The .py twins" above
pytest tests/test_cli_pair.py tests/test_cli_run.py tests/test_cli_demo_notebook.py

# the magic tests, headless
jlx run tests/test_extract_magic.ipynb

# the demo, headless -- regenerates its outputs and extracted file
jlx run tests/demo_plots.ipynb
```

The magic tests can also be run by opening `test_extract_magic.ipynb` in
JupyterLab and running all cells; failures surface as normal pytest assertion
errors in the cell output. To run one in isolation, run just that cell — each
`%%ipytest` block redefines its own test function, so the cells are independent.
