"""
jupyter_lab_extractor

A Jupyter cell magic that extracts cell contents to Python files
while running the cell normally. Each extracted block includes a
metadata comment header with notebook path, cell number, and timestamp.

Usage:
    %load_ext jupyter_lab_extractor

    %%extract myfile.py
    # Overwrites myfile.py (default is -w)

    %%extract myfile.py -a
    # Appends to myfile.py

    %%extract myfile.py -w
    # Explicitly overwrite

    %%extract myfile.py -a --strip-ipytest
    # Appends, dropping ipytest.clean()/run()/autoconfig() scaffolding lines

    %%extract a.py,pkg/b.py
    # Writes the same contents to several files (comma-separated, no spaces)
"""

# pip install ipynbname
from IPython.core.getipython import get_ipython
from datetime import datetime
import re
import os

# `jlx run` sets this before starting the kernel. ipynbname identifies the
# notebook by asking a running Jupyter server which one owns the kernel, so it
# cannot work headless -- without this the header would read "unknown_path".
_NB_PATH_ENV_VAR = "JUPYTER_LAB_EXTRACTOR_NB_PATH"

_NOTEBOOK_REL_PATH = os.environ.get(_NB_PATH_ENV_VAR) or ""
if _NOTEBOOK_REL_PATH:
    _NOTEBOOK_NAME = os.path.splitext(os.path.basename(_NOTEBOOK_REL_PATH))[0]
else:
    try:
        from ipynbname import _find_nb_path
        _, _nb_path = _find_nb_path()
        _NOTEBOOK_NAME = _nb_path.stem if _nb_path else "unknown_notebook"
        _NOTEBOOK_REL_PATH = str(_nb_path) if _nb_path else "unknown_path"
    except Exception:
        _NOTEBOOK_NAME = "unknown_notebook"
        _NOTEBOOK_REL_PATH = "unknown_path"


_USAGE = "Usage: %%extract filename.py [-w|-a] [--strip-ipytest]"

_KNOWN_FLAGS = {'-w', '-a', '--strip-ipytest'}

# Magic invocations (% or %%) -- meaningless in a plain .py file.
_MAGIC_RE = re.compile(r'^\s*%%?[a-zA-Z]')

# ipytest scaffolding calls. These drive the in-notebook test runner; left in an
# extracted file they would wipe or re-run the collected tests at import time.
_IPYTEST_SCAFFOLD_RE = re.compile(r'^\s*ipytest\.(clean|clean_tests|run|autoconfig)\s*\(')


def _clean_cell(cell, strip_ipytest=False):
    """
    Turn raw cell source into what gets written to the target file.

    Always drops magic lines. With strip_ipytest, also drops ipytest
    scaffolding calls and the blank padding they leave behind, so that
    cells appended with -a stack into one clean, importable module.
    """
    lines = [ln for ln in cell.splitlines() if not _MAGIC_RE.match(ln)]

    if strip_ipytest:
        lines = [ln for ln in lines if not _IPYTEST_SCAFFOLD_RE.match(ln)]
        # Removing the scaffolding strands blank lines at the block edges;
        # trimming them keeps appended blocks from drifting apart.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

    return '\n'.join(lines) + '\n'


def extract(line, cell):
    """
    A cell magic that extracts cell contents to a file, then runs the cell normally.
    Each extracted block gets a metadata comment header.

    Usage:
        %%extract myfile.py
        # Overwrites myfile.py (default is -w)

        %%extract myfile.py -w
        # Explicitly overwrite

        %%extract myfile.py -a
        # Append to myfile.py

        %%extract myfile.py -a --strip-ipytest
        # Append, dropping ipytest.clean()/run()/autoconfig() lines so that
        # repeated clean/run cells stack into one importable test module

        %%extract a.py,pkg/b.py
        # Write the same contents to several files. Separate paths with commas
        # and no spaces; -w/-a apply to every file. File names containing a
        # comma are not supported.
    """
    args = line.strip().split()
    if not args:
        raise ValueError("You must specify a target file. " + _USAGE)

    flags = [a for a in args if a.startswith('-')]
    files = [a for a in args if not a.startswith('-')]

    if not files:
        raise ValueError("You must specify a target file. " + _USAGE)

    unknown = [f for f in flags if f not in _KNOWN_FLAGS]
    if unknown:
        # Silently ignoring a typo'd flag would quietly write the wrong contents.
        raise ValueError(f"Unknown flag(s): {' '.join(unknown)}. " + _USAGE)

    if len(files) > 1:
        # Dropping the extra paths silently would leave a file unwritten.
        raise ValueError(
            f"Got {len(files)} separate paths: {' '.join(files)}. "
            "To write several files, separate them with commas and no spaces "
            "(a.py,b.py). " + _USAGE
        )

    targets = files[0].split(',')
    if not all(targets):
        raise ValueError(
            f"Empty file name in target list {files[0]!r} "
            "(doubled or trailing comma). " + _USAGE
        )
    mode = 'a' if '-a' in flags else 'w'

    cleaned = _clean_cell(cell, strip_ipytest='--strip-ipytest' in flags)

    # Build metadata header
    exec_count = get_ipython().execution_count
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"# Source: {_NOTEBOOK_REL_PATH} | Cell In[{exec_count}] | {timestamp}\n"

    # Same header, contents and mode for every target.
    for target in targets:
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(target) or '.', exist_ok=True)

        with open(target, mode, encoding="utf-8") as f:
            f.write(header)
            f.write(cleaned)
            f.write('\n')

    # Execute the cell normally
    get_ipython().run_cell(cell)


def load_ipython_extension(ipython):
    """Called by %load_ext jupyter_lab_extractor"""
    ipython.register_magic_function(extract, "cell", "extract")


# Registering at import time as well keeps a bare `import jupyter_lab_extractor`
# working in a kernel without %load_ext. Outside IPython -- the jlx CLI, plain
# pytest -- there is no shell, and importing the package must stay harmless.
_ip = get_ipython()
if _ip is not None:
    load_ipython_extension(_ip)
