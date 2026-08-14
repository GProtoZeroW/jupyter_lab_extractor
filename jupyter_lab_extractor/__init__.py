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
"""

# pip install ipynbname
from IPython.core.magic import register_cell_magic
from datetime import datetime
import re
import os

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


@register_cell_magic
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

    target = files[0]
    mode = 'a' if '-a' in flags else 'w'

    cleaned = _clean_cell(cell, strip_ipytest='--strip-ipytest' in flags)

    # Build metadata header
    exec_count = get_ipython().execution_count
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"# Source: {_NOTEBOOK_REL_PATH} | Cell In[{exec_count}] | {timestamp}\n"

    # Ensure parent directories exist
    os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
    
    # Write to the target file
    with open(target, mode, encoding="utf-8") as f:
        f.write(header)
        f.write(cleaned)
        f.write('\n')

    # Execute the cell normally
    get_ipython().run_cell(cell)


def load_ipython_extension(ipython):
    """Called by %load_ext jupyter_lab_extractor"""
    # The @register_cell_magic decorator already registers it at import time,
    # but this function is needed for %load_ext to work without error.
    pass
