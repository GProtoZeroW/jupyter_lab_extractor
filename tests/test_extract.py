# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # jupyter_lab_extractor — Test Notebook
#
# This notebook tests the `%%extract` cell magic from the `jupyter_lab_extractor` package.
#
# **Note:** This notebook is paired with a `.py`  script via Jupytext.
# Always run from the `.ipynb` — the `.py` file is for version control / diffing only.
# Running the `.py` directly will not work since cell magics require a live Jupyter kernel.

# %% [markdown] jp-MarkdownHeadingCollapsed=true
# ## What this notebook covers
# 1. Writing cell contents to a new file
# 2. Appending to an existing file with `-a`
# 3. Overwriting an existing file (default `-w` behavior)
# 4. Metadata headers and magic line stripping
# 5. Error handling

# %% [markdown]
# ---
# # Setup

# %% [markdown]
# ## Logging with Loguru
# Provides visibility into what is happening during test execution.

# %%
# Logging configuration
# Log levels from most output to least (severity low to high):
# TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
CONSOLE_LOG_LEVEL = "DEBUG"
FILE_LOG_LEVEL = "DEBUG"

from loguru import logger
from pathlib import Path
import sys

# Remove default handler to avoid duplicates
logger.remove()

# Configure log file
LOG_FILE = Path.cwd() / "test_extract_debug.log"

# Clear existing log file to start fresh each run
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Console handler configuration - colorful output for Jupyter
console_handler_id = logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | <level>{message}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <green>{time:HH:mm:ss.SSS}</green>",
    level=CONSOLE_LOG_LEVEL,
    colorize=True,
    enqueue=False,  # Must be False for Jupyter compatibility
    backtrace=True,
    diagnose=True
)

# File handler configuration - single file, overwritten each run
file_handler_id = logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.id}:{thread.id} | {name}:{function}:{line} | {message}",
    level=FILE_LOG_LEVEL,
    enqueue=True,  # Thread-safe for file operations
    backtrace=True,
    diagnose=True
)

logger.success("Loguru configured successfully")
logger.info(f"Log file: {LOG_FILE.absolute()}")
logger.info(f"Console handler ID: {console_handler_id}, File handler ID: {file_handler_id}")

# %% [markdown]
# ## Imports and ipytest Configuration

# %%
import os
import shutil
import ipytest
ipytest.autoconfig()

logger.success("ipytest configured")

# %% [markdown]
# ## Load the `%%extract` Magic

# %%
# %load_ext jupyter_lab_extractor
logger.success("jupyter_lab_extractor magic loaded")

# %% [markdown]
# ---
# # Superficial Usage Tests
# These cells use `%%extract` as a user would in a real notebook,
# then verify the output with ipytest.

# %% [markdown]
# ## Test 1: Write Cell Contents to a New File
# The default behavior (`-w`) should create a new file with the cell contents
# and a metadata header comment.

# %%
# %%extract test_output_1.py
x = 42
y = "hello"

# %%
logger.info("Wrote test_output_1.py — checking contents:")
logger.debug(open("test_output_1.py").read())

# %%
# %%ipytest

def test_write_new_file():
    content = open("test_output_1.py").read()
    assert "x = 42" in content
    assert 'y = "hello"' in content
    assert "# Source:" in content

# %% [markdown]
# ## Test 2: Write Then Append
# First cell creates `test_output_2.py`, second cell appends to it with `-a`.
# The result should contain both blocks with two metadata headers.

# %% [markdown]
# ### Write the initial file

# %%
# %%extract test_output_2.py
import os
CONSTANT = 100

# %%
logger.info("Wrote test_output_2.py — initial block")

# %% [markdown]
# ### Append a second block

# %%
# %%extract test_output_2.py -a
def helper():
    return CONSTANT * 2

# %%
logger.info("Appended to test_output_2.py — checking contents:")
logger.debug(open("test_output_2.py").read())

# %% [markdown]
# ### Confirm both blocks are present

# %%
# %%ipytest

def test_write_then_append():
    content = open("test_output_2.py").read()
    assert "import os" in content
    assert "CONSTANT = 100" in content
    assert "def helper():" in content
    assert "return CONSTANT * 2" in content
    assert content.count("# Source:") == 2

# %% [markdown]
# ## Test 3: Overwrite Replaces Existing Content
# Copy `test_output_2.py` (which has two blocks), then overwrite the copy.
# The old content should be completely gone.

# %% [markdown]
# ### Make a copy to work with

# %%
shutil.copy("test_output_2.py", "test_output_2_copy.py")
logger.info("Copied test_output_2.py -> test_output_2_copy.py")

# %% [markdown]
# ### Overwrite the copy with new content

# %%
# %%extract test_output_2_copy.py
completely_new = True

# %%
logger.info("Overwrote test_output_2_copy.py — checking contents:")
logger.debug(open("test_output_2_copy.py").read())

# %% [markdown]
# ### Confirm old content is gone

# %%
# %%ipytest

def test_overwrite_copy():
    content = open("test_output_2_copy.py").read()
    assert "completely_new = True" in content
    assert "CONSTANT" not in content
    assert "def helper" not in content
    assert content.count("# Source:") == 1

# %% [markdown]
# ---
# # Deeper Unit Tests
# These use `tmp_path` fixtures and `run_cell_magic()` directly
# for more isolated testing.

# %% [markdown]
# ## Overwrite Mode (default)

# %%
# %%ipytest

import os

def test_extract_overwrite(tmp_path):
    """Test that default mode overwrites the file"""
    target = str(tmp_path / "out.py")
    ip = get_ipython()

    # Write something first
    with open(target, 'w') as f:
        f.write("old content\n")

    ip.run_cell_magic('extract', target, 'x = 1')

    content = open(target).read()
    assert "old content" not in content
    assert "x = 1" in content
    assert "# Source:" in content

# %% [markdown]
# ## Append Mode (`-a`)

# %%
# %%ipytest

def test_extract_append(tmp_path):
    """Test that -a appends to the file"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    ip.run_cell_magic('extract', target, 'x = 1')
    ip.run_cell_magic('extract', f'{target} -a', 'y = 2')

    content = open(target).read()
    assert "x = 1" in content
    assert "y = 2" in content
    assert content.count("# Source:") == 2

# %% [markdown]
# ## Magic Lines Are Stripped

# %%
# %%ipytest

def test_magic_lines_stripped(tmp_path):
    """Test that % and %% magic lines are removed from output"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    cell_content = "%matplotlib inline\nimport numpy as np\n%%time\nx = 1"
    ip.run_cell_magic('extract', target, cell_content)

    content = open(target).read()
    assert "matplotlib" not in content
    assert "%%time" not in content
    assert "import numpy as np" in content
    assert "x = 1" in content

# %% [markdown]
# ## Missing Filename Raises Error

# %%
# %%ipytest

import pytest

def test_extract_no_filename():
    """Test that missing filename raises ValueError"""
    ip = get_ipython()
    with pytest.raises(ValueError):
        ip.run_cell_magic('extract', '', 'x = 1')

# %% [markdown]
# ## Metadata Header Format

# %%
# %%ipytest

def test_metadata_header(tmp_path):
    """Test that header contains expected metadata fields"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    ip.run_cell_magic('extract', target, 'x = 1')

    content = open(target).read()
    header = content.splitlines()[0]
    assert header.startswith("# Source:")
    assert "Cell In[" in header
    assert "|" in header

# %% [markdown]
# ---
# ## Extract + ipytest Combo (BROKEN — needs `os.makedirs` fix)
# This cell attempts to both extract itself to a file AND run as a test.
# Currently fails because `%%extract` does not create parent directories.
# Leaving as-is until the fix is applied.

# %%
# # %%extract tests/extracted_test.py
# # %%ipytest

# def test_round_trip():
#     """This test was both run by ipytest AND extracted to a file"""
#     assert 1 + 1 == 2
#     assert "hello".upper() == "HELLO"

# %%
