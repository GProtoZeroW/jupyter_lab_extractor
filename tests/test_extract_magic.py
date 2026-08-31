# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
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
# **Note:** This notebook is paired with a `.py` script via Jupytext.
# Always run from the `.ipynb` — the `.py` file is for version control / diffing only.
# Running the `.py` directly will not work since cell magics require a live Jupyter kernel.

# %% [markdown] jp-MarkdownHeadingCollapsed=true
# ## What this notebook covers
# 1. Writing cell contents to a new file
# 2. Appending to an existing file with `-a`
# 3. Overwriting an existing file (default `-w` behavior)
# 4. Using `%%extract` and `%%ipytest` together on the same cell
# 5. Metadata headers and magic line stripping
# 6. Error handling

# %% [markdown]
# ---
# # Setup

# %% [markdown]
# ## Logging with the standard library
# Provides visibility into what is happening during test execution.

# %%
# Logging configuration
# Log levels from most output to least (severity low to high):
# TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
CONSOLE_LOG_LEVEL = "DEBUG"
FILE_LOG_LEVEL = "DEBUG"

import logging
import sys
from datetime import datetime
from pathlib import Path

# stdlib logging has no TRACE or SUCCESS level. loguru puts SUCCESS at 25,
# between INFO (20) and WARNING (30), and TRACE at 5, below DEBUG (10).
# Register both and hang matching methods off Logger so that call sites read
# exactly as they did under loguru: logger.success("..."), logger.trace("...").
TRACE = 5
SUCCESS = 25
logging.addLevelName(TRACE, "TRACE")
logging.addLevelName(SUCCESS, "SUCCESS")


def _log_at(level):
    def method(self, message, *args, **kwargs):
        if self.isEnabledFor(level):
            # stacklevel=2 steps past this wrapper so that {function} and
            # {line} name the caller, the way loguru reports them.
            kwargs.setdefault("stacklevel", 2)
            self._log(level, message, args, **kwargs)
    return method


logging.Logger.trace = _log_at(TRACE)
logging.Logger.success = _log_at(SUCCESS)

# loguru's default level colours, as raw ANSI escapes.
_LEVEL_COLOR = {
    "TRACE": "\033[36m\033[1m",     # cyan bold
    "DEBUG": "\033[34m\033[1m",     # blue bold
    "INFO": "\033[1m",              # bold
    "SUCCESS": "\033[32m\033[1m",   # green bold
    "WARNING": "\033[33m\033[1m",   # yellow bold
    "ERROR": "\033[31m\033[1m",     # red bold
    "CRITICAL": "\033[41m\033[1m",  # red background, bold
}
_RESET = "\033[0m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"


class ConsoleFormatter(logging.Formatter):
    """LEVEL    | message | name:function | HH:MM:SS.mmm

    Mirrors the loguru console format this notebook used to configure:
    <level>{level: <8}</level> | <level>{message}</level> |
    <cyan>{name}</cyan>:<cyan>{function}</cyan> | <green>{time:HH:mm:ss.SSS}</green>
    """

    def format(self, record):
        color = _LEVEL_COLOR.get(record.levelname, "")
        stamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        return (
            f"{color}{record.levelname: <8}{_RESET} | "
            f"{color}{record.getMessage()}{_RESET} | "
            f"{_CYAN}{record.name}{_RESET}:{_CYAN}{record.funcName}{_RESET} | "
            f"{_GREEN}{stamp}{_RESET}"
        )


class FileFormatter(logging.Formatter):
    """YYYY-MM-DD HH:MM:SS.mmm | LEVEL    | pid:tid | name:function:line | message"""

    def format(self, record):
        stamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return (
            f"{stamp} | {record.levelname: <8} | "
            f"{record.process}:{record.thread} | "
            f"{record.name}:{record.funcName}:{record.lineno} | "
            f"{record.getMessage()}"
        )


# Configure log file
LOG_FILE = Path.cwd() / "test_extract_debug.log"

# Clear existing log file to start fresh each run
if LOG_FILE.exists():
    LOG_FILE.unlink()

logger = logging.getLogger("test_extract_magic")

# The logger passes everything through; each handler applies its own level,
# the way a loguru sink does.
logger.setLevel(TRACE)

# Re-running this cell must not stack duplicate handlers. This is the
# equivalent of loguru's logger.remove().
for _handler in list(logger.handlers):
    logger.removeHandler(_handler)
    _handler.close()

# Records stop here; without this the root logger would print them a second time.
logger.propagate = False

# Console handler configuration - colorful output for Jupyter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(CONSOLE_LOG_LEVEL)
console_handler.setFormatter(ConsoleFormatter())
logger.addHandler(console_handler)

# File handler configuration - single file, overwritten each run.
# stdlib handlers already lock around emit, so loguru's enqueue=True has no
# counterpart to configure here.
file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
file_handler.setLevel(FILE_LOG_LEVEL)
file_handler.setFormatter(FileFormatter())
logger.addHandler(file_handler)

logger.success("Logging configured successfully")
logger.info(f"Log file: {LOG_FILE.absolute()}")
logger.info(f"Console level: {CONSOLE_LOG_LEVEL}, file level: {FILE_LOG_LEVEL}")

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
# ## Prepare Output Directory
# All extracted files go into a subfolder to keep the test directory clean.

# %%
OUTPUT_DIR = Path("test_demo_outputs")
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
    logger.debug(f"Cleared existing {OUTPUT_DIR}/")
OUTPUT_DIR.mkdir(exist_ok=True)
logger.success(f"Output directory ready: {OUTPUT_DIR}/")

# %% [markdown]
# # Usage Examples (with quick confirm test)
# These cells use `%%extract` as a user would in a real notebook,
# then verify the output with ipytest.

# %% [markdown]
# ## Test 1: Write Cell Contents to a New File
# The default behavior (`-w`) should create a new file with the cell contents
# and a metadata header comment.

# %%
# %%extract test_demo_outputs/test_output_1.py
x = 42
y = "hello"

# %%
logger.info("Wrote test_demo_outputs/test_output_1.py — checking contents:")
logger.debug(open("test_demo_outputs/test_output_1.py").read())

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_write_new_file():
    content = open("test_demo_outputs/test_output_1.py").read()
    assert "x = 42" in content
    logger.debug("Found 'x = 42'")
    assert 'y = "hello"' in content
    logger.debug("Found 'y = \"hello\"'")
    assert "# Source:" in content
    logger.debug("Found metadata header")
    logger.success("test_write_new_file passed")

# %% [markdown]
# ## Test 2: Write Then Append
# First cell creates `test_output_2.py`, second cell appends to it with `-a`.
# The result should contain both blocks with two metadata headers.

# %% [markdown]
# ### Write the initial file

# %%
# %%extract test_demo_outputs/test_output_2.py
import os
CONSTANT = 100

# %%
logger.info("Wrote test_demo_outputs/test_output_2.py — initial block")

# %% [markdown]
# ### Append a second block

# %%
# %%extract test_demo_outputs/test_output_2.py -a
def helper():
    return CONSTANT * 2

# %%
logger.info("Appended to test_demo_outputs/test_output_2.py — checking contents:")
logger.debug(open("test_demo_outputs/test_output_2.py").read())

# %% [markdown]
# ### Confirm both blocks are present

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_write_then_append():
    content = open("test_demo_outputs/test_output_2.py").read()
    assert "import os" in content
    logger.debug("Found 'import os'")
    assert "CONSTANT = 100" in content
    logger.debug("Found 'CONSTANT = 100'")
    assert "def helper():" in content
    logger.debug("Found 'def helper():'")
    assert "return CONSTANT * 2" in content
    logger.debug("Found 'return CONSTANT * 2'")
    assert content.count("# Source:") == 2
    logger.debug("Found 2 metadata headers")
    logger.success("test_write_then_append passed")

# %% [markdown]
# ## Test 3: Overwrite Replaces Existing Content
# Copy `test_output_2.py` (which has two blocks), then overwrite the copy.
# The old content should be completely gone.

# %% [markdown]
# ### Make a copy to work with

# %%
shutil.copy("test_demo_outputs/test_output_2.py", "test_demo_outputs/test_output_2_copy.py")
logger.info("Copied test_output_2.py -> test_output_2_copy.py")

# %% [markdown]
# ### Overwrite the copy with new content

# %%
# %%extract test_demo_outputs/test_output_2_copy.py
completely_new = True

# %%
logger.info("Overwrote test_demo_outputs/test_output_2_copy.py — checking contents:")
logger.debug(open("test_demo_outputs/test_output_2_copy.py").read())

# %% [markdown]
# ### Confirm old content is gone

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_overwrite_copy():
    content = open("test_demo_outputs/test_output_2_copy.py").read()
    assert "completely_new = True" in content
    logger.debug("Found 'completely_new = True'")
    assert "CONSTANT" not in content
    logger.debug("Confirmed old 'CONSTANT' is gone")
    assert "def helper" not in content
    logger.debug("Confirmed old 'def helper' is gone")
    assert content.count("# Source:") == 1
    logger.debug("Found exactly 1 metadata header")
    logger.success("test_overwrite_copy passed")

# %% [markdown]
# ## Test 4: Extract + ipytest Combo
# This cell is both extracted to a file AND run as a test simultaneously.
# Demonstrates that `%%extract` does not interfere with cell execution,
# even when another cell magic (`%%ipytest`) is present in the cell body.

# %%
# %%extract test_demo_outputs/extracted_test.py
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_round_trip():
    """This test was both run by ipytest AND extracted to a file"""
    assert 1 + 1 == 2
    logger.debug("1 + 1 == 2")
    assert "hello".upper() == "HELLO"
    logger.debug("'hello'.upper() == 'HELLO'")
    logger.success("test_round_trip passed — cell was extracted and executed")

# %%
logger.info("Checking extracted_test.py contents:")
logger.debug(open("test_demo_outputs/extracted_test.py").read())

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
import logging
logger = logging.getLogger("test_extract_magic")

def test_extract_overwrite(tmp_path):
    """Test that default mode overwrites the file"""
    target = str(tmp_path / "out.py")
    ip = get_ipython()

    # Write something first
    with open(target, 'w') as f:
        f.write("old content\n")
    logger.debug(f"Wrote 'old content' to {target}")

    ip.run_cell_magic('extract', target, 'x = 1')
    logger.debug(f"Ran %%extract on {target}")

    content = open(target).read()
    assert "old content" not in content
    logger.debug("Confirmed 'old content' was overwritten")
    assert "x = 1" in content
    logger.debug("Found 'x = 1'")
    assert "# Source:" in content
    logger.debug("Found metadata header")
    logger.success("test_extract_overwrite passed")

# %% [markdown]
# ## Append Mode (`-a`)

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_extract_append(tmp_path):
    """Test that -a appends to the file"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    ip.run_cell_magic('extract', target, 'x = 1')
    logger.debug(f"Wrote first block to {target}")
    ip.run_cell_magic('extract', f'{target} -a', 'y = 2')
    logger.debug(f"Appended second block to {target}")

    content = open(target).read()
    assert "x = 1" in content
    assert "y = 2" in content
    assert content.count("# Source:") == 2
    logger.debug("Found both blocks and 2 metadata headers")
    logger.success("test_extract_append passed")

# %% [markdown]
# ## Magic Lines Are Stripped

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_magic_lines_stripped(tmp_path):
    """Test that % and %% magic lines are removed from output"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    cell_content = "%matplotlib inline\nimport numpy as np\n%%time\nx = 1"
    ip.run_cell_magic('extract', target, cell_content)
    logger.debug(f"Extracted cell with mixed magic lines to {target}")

    content = open(target).read()
    assert "matplotlib" not in content
    logger.debug("Confirmed '%matplotlib inline' was stripped")
    assert "%%time" not in content
    logger.debug("Confirmed '%%time' was stripped")
    assert "import numpy as np" in content
    logger.debug("Confirmed 'import numpy as np' was kept")
    assert "x = 1" in content
    logger.debug("Confirmed 'x = 1' was kept")
    logger.success("test_magic_lines_stripped passed")

# %% [markdown]
# ## Missing Filename Raises Error

# %%
# %%ipytest

import pytest
import logging
logger = logging.getLogger("test_extract_magic")

def test_extract_no_filename():
    """Test that missing filename raises ValueError"""
    ip = get_ipython()
    with pytest.raises(ValueError):
        ip.run_cell_magic('extract', '', 'x = 1')
    logger.success("test_extract_no_filename passed — ValueError raised as expected")

# %% [markdown]
# ## Metadata Header Format

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")

def test_metadata_header(tmp_path):
    """Test that header contains expected metadata fields"""
    target = str(tmp_path / "out.py")

    ip = get_ipython()
    ip.run_cell_magic('extract', target, 'x = 1')

    content = open(target).read()
    header = content.splitlines()[0]
    logger.debug(f"Header: {header}")
    assert header.startswith("# Source:")
    logger.debug("Header starts with '# Source:'")
    assert "Cell In[" in header
    logger.debug("Header contains cell execution number")
    assert "|" in header
    logger.debug("Header contains pipe delimiters")
    logger.success("test_metadata_header passed")

# %% [markdown]
# ---
# # Feature: `--strip-ipytest`
#
# `ipytest.clean()` and `ipytest.run()` drive the *in-notebook* test runner.
# Left in an extracted file they would wipe or re-run the collected tests at
# import time, so `--strip-ipytest` drops them (along with `clean_tests()` and
# `autoconfig()`) and trims the blank padding they leave behind.
#
# That is what lets many clean/define/run cells stack via `-a` into a single
# importable test module.

# %% [markdown]
# ## Unit tests on the cleaning logic
# `_clean_cell` is the pure function behind the magic. Testing it directly
# avoids executing `ipytest.clean()`/`ipytest.run()` as a side effect of a test.

# %%
# %%ipytest

from jupyter_lab_extractor import _clean_cell
import logging
logger = logging.getLogger("test_extract_magic")

CLEAN_RUN_CELL = (
    "ipytest.clean()\n"
    "\n"
    "\n"
    "def test_example(unbounded):\n"
    "    unbounded.requested_value = 1.234567891e9\n"
    "    assert float(unbounded.requested_value_scpi) == 1.234567891e9\n"
    "\n"
    "\n"
    "ipytest.run()\n"
)


def test_strip_removes_clean_and_run():
    out = _clean_cell(CLEAN_RUN_CELL, strip_ipytest=True)
    assert "ipytest.clean" not in out
    logger.debug("ipytest.clean() removed")
    assert "ipytest.run" not in out
    logger.debug("ipytest.run() removed")
    assert "def test_example(unbounded):" in out
    logger.debug("test body kept")
    logger.success("test_strip_removes_clean_and_run passed")


def test_strip_trims_blank_padding():
    """Dropping the scaffolding must not leave blank lines at the block edges."""
    out = _clean_cell(CLEAN_RUN_CELL, strip_ipytest=True)
    assert not out.startswith("\n")
    logger.debug("no leading blank line")
    assert not out.rstrip("\n").endswith("\n")
    logger.debug("no trailing blank padding")
    logger.success("test_strip_trims_blank_padding passed")


def test_without_flag_scaffolding_is_kept():
    """Default behavior is unchanged -- stripping is opt-in."""
    out = _clean_cell(CLEAN_RUN_CELL)
    assert "ipytest.clean()" in out
    assert "ipytest.run()" in out
    logger.debug("scaffolding preserved when flag is absent")
    logger.success("test_without_flag_scaffolding_is_kept passed")


def test_strip_covers_all_scaffolding_variants():
    cell = "ipytest.autoconfig()\nipytest.clean_tests()\nx = 1\nipytest.run('-qq')\n"
    out = _clean_cell(cell, strip_ipytest=True)
    assert "autoconfig" not in out
    logger.debug("autoconfig() removed")
    assert "clean_tests" not in out
    logger.debug("clean_tests() removed")
    assert "ipytest.run" not in out
    logger.debug("run() with arguments removed")
    assert "x = 1" in out
    logger.debug("surrounding code kept")
    logger.success("test_strip_covers_all_scaffolding_variants passed")


def test_magic_lines_still_stripped_with_flag():
    cell = "%%ipytest\nimport os\nipytest.run()\n"
    out = _clean_cell(cell, strip_ipytest=True)
    assert "%%ipytest" not in out
    logger.debug("magic line still stripped alongside ipytest calls")
    assert "import os" in out
    logger.success("test_magic_lines_still_stripped_with_flag passed")

# %% [markdown]
# ## A mistyped flag is rejected
# Silently ignoring an unknown flag would quietly write the wrong file contents.

# %%
# %%ipytest

import pytest
import logging
logger = logging.getLogger("test_extract_magic")


def test_unknown_flag_raises():
    ip = get_ipython()
    with pytest.raises(ValueError, match="Unknown flag"):
        ip.run_cell_magic('extract', 'never_written.py --strip-ipytests', 'x = 1')
    logger.success("test_unknown_flag_raises passed -- typo rejected before writing")

# %% [markdown]
# ## End-to-end: stacking clean/run cells into one file
# These cells use `%%extract` exactly as a user would. Each one cleans, defines
# a test, and runs it *in the notebook*, while the extracted file accumulates
# only the test definitions.

# %%
# %%extract test_demo_outputs/test_stacked.py --strip-ipytest
ipytest.clean()


def test_stacked_one():
    assert True


ipytest.run()

# %%
# %%extract test_demo_outputs/test_stacked.py -a --strip-ipytest
ipytest.clean()


def test_stacked_two():
    assert 1 + 1 == 2


ipytest.run()

# %%
# %%extract test_demo_outputs/test_stacked.py -a --strip-ipytest
ipytest.clean()


def test_stacked_three():
    assert "a".upper() == "A"


ipytest.run()

# %%
logger.info("Stacked three cells into test_demo_outputs/test_stacked.py:")
logger.debug(open("test_demo_outputs/test_stacked.py").read())

# %% [markdown]
# ### Confirm the stacked file is clean and importable

# %%
# %%ipytest

import logging
logger = logging.getLogger("test_extract_magic")


def test_stacked_file_is_clean_and_importable():
    content = open("test_demo_outputs/test_stacked.py").read()

    assert content.count("# Source:") == 3
    logger.debug("Found 3 metadata headers -- one per cell")
    assert "ipytest." not in content
    logger.debug("No ipytest scaffolding survived into the file")

    for name in ("test_stacked_one", "test_stacked_two", "test_stacked_three"):
        assert f"def {name}():" in content
        logger.debug(f"Found {name}")

    # The whole point of the flag: the result must be valid, importable Python.
    namespace = {}
    exec(compile(content, "test_stacked.py", "exec"), namespace)
    collected = sorted(n for n in namespace if n.startswith("test_"))
    assert collected == ["test_stacked_one", "test_stacked_three", "test_stacked_two"]
    logger.debug(f"All three tests importable: {collected}")
    logger.success("test_stacked_file_is_clean_and_importable passed")

# %%
