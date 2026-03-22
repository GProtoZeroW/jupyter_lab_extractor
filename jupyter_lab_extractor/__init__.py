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
    """
    args = line.strip().split()
    if not args:
        raise ValueError("You must specify a target file: %%extract filename.py [-w|-a]")

    flags = [a for a in args if a.startswith('-')]
    files = [a for a in args if not a.startswith('-')]

    if not files:
        raise ValueError("You must specify a target file: %%extract filename.py [-w|-a]")

    target = files[0]
    mode = 'a' if '-a' in flags else 'w'

    # Strip out any lines that are magic commands (% or %%)
    cleaned_lines = [
        ln for ln in cell.splitlines()
        if not re.match(r'^\s*%%?[a-zA-Z]', ln)
    ]
    cleaned = '\n'.join(cleaned_lines) + '\n'

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
