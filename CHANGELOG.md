# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-31

First release.

### Added

- `%%extract <path> [-w|-a] [--strip-ipytest]` cell magic. Writes a cell's
  contents to a `.py` file *and* runs the cell normally, so the notebook stays
  executable. `-w` overwrites (the default), `-a` appends, and unknown flags
  raise rather than silently writing the wrong contents.
- A `# Source: <notebook> | Cell In[<n>] | <timestamp>` provenance header on
  every extracted block, and automatic creation of parent directories.
- Magic-line stripping, so `%%extract` and `%%ipytest` can share a cell while
  the exported file stays importable.
- `--strip-ipytest`, which additionally drops `ipytest.clean()`,
  `clean_tests()`, `run()` and `autoconfig()` calls plus the blank padding they
  strand, so repeated clean/define/run cells stack via `-a` into one clean
  pytest module.
- `jlx run NOTEBOOK`, which executes notebooks headlessly the way the browser
  does: cells run, `%%extract` writes its files, and outputs including
  matplotlib figures are saved back into the `.ipynb`. Accepts files and
  directories, stops at the first failing cell but still writes the notebook so
  the traceback stays visible, and exits non-zero if anything failed.
- `jlx pair NOTEBOOK`, which establishes a Jupytext `ipynb,py:percent` pairing
  when none exists. It leaves an established pairing alone and refuses when both
  halves exist unpaired rather than overwriting one side.
- `--kernel`, `--timeout`, `--allow-errors` and `--check` flags on `jlx run`.
- A `cli` extra carrying jupytext, nbclient, nbformat and ipykernel. The base
  install needs only IPython and ipynbname.

### Notes

- `%%extract` always writes the file, even when the cell raises. The export is a
  copy of the cell's contents, not a record of whether they worked.
