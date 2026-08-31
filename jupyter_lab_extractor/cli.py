"""
Command line interface for jupyter_lab_extractor.

    jlx pair NOTEBOOK
    jlx run  NOTEBOOK [NOTEBOOK ...]

`pair` establishes a Jupytext ipynb/py:percent pairing for a notebook that does
not already have one. If a pairing is already established, nothing is touched --
Jupytext (or the Lab plugin) is already keeping the two sides in step.

`run` executes notebooks headlessly, the way running them in the browser would:
%%extract fires, plots and other cell outputs are produced and saved back into
the .ipynb, and the first error stops the run and is reported.
"""

import argparse
import os
import sys
from pathlib import Path

# The pairing this tool sets up. Matches what tests/test_extract_magic.ipynb
# already uses, so `jlx pair` on it is a no-op.
PAIRED_FORMATS = "ipynb,py:percent"

_INSTALL_HINT = (
    "jlx needs Jupytext. Install it with:\n"
    "    pip install jupyter-lab-extractor[cli]"
)

_RUN_INSTALL_HINT = (
    "jlx run needs nbclient and nbformat. Install them with:\n"
    "    pip install jupyter-lab-extractor[cli]"
)

# Handed to the kernel by run_one() so %%extract can name its source notebook.
NB_PATH_ENV_VAR = "JUPYTER_LAB_EXTRACTOR_NB_PATH"


class PairError(Exception):
    """A pairing request that cannot be satisfied without destroying content."""


class RunError(Exception):
    """A run request that cannot be carried out at all (as opposed to a
    notebook that ran and failed -- that is reported per notebook)."""


def _import_jupytext():
    try:
        import jupytext
    except ImportError:
        raise PairError(_INSTALL_HINT)
    return jupytext


def counterpart(path):
    """The other half of an ipynb/py pair: same stem, other extension."""
    stem, ext = os.path.splitext(path)
    if ext == ".ipynb":
        return stem + ".py"
    if ext == ".py":
        return stem + ".ipynb"
    raise PairError(f"Expected a .ipynb or .py file, got: {path}")


def _config_declares_pairing(path):
    """True if a jupytext.toml / pyproject.toml in scope sets up the pairing."""
    try:
        from jupytext.config import find_jupytext_configuration_file
    except ImportError:
        return False
    directory = os.path.dirname(os.path.abspath(path))
    try:
        return find_jupytext_configuration_file(directory) is not None
    except Exception:
        # A malformed config elsewhere on disk is not this tool's problem;
        # fall back to metadata-only detection.
        return False


def is_paired(path):
    """True if `path` already has an established Jupytext pairing."""
    jupytext = _import_jupytext()
    nb = jupytext.read(path)
    if nb.metadata.get("jupytext", {}).get("formats"):
        return True
    return _config_declares_pairing(path)


def pair(path):
    """
    Establish an ipynb/py:percent pairing for `path` if one does not exist.

    Returns a human-readable summary of what happened. Raises PairError when
    both halves exist but are unpaired -- syncing either direction would
    silently overwrite the other side's content, so that is the user's call.
    """
    jupytext = _import_jupytext()

    if not os.path.isfile(path):
        raise PairError(f"No such file: {path}")

    other = counterpart(path)

    if is_paired(path):
        return f"Already paired, nothing to do: {path}"

    if os.path.isfile(other):
        raise PairError(
            f"Both {path} and {other} exist but are not paired.\n"
            "Syncing either direction would overwrite the other side. Decide "
            "which file is authoritative and pair it yourself:\n"
            f"    jupytext --set-formats {PAIRED_FORMATS} <authoritative file>"
        )

    nb = jupytext.read(path)
    metadata = nb.metadata.setdefault("jupytext", {})

    # A text file with no YAML header reads back with a "-all" metadata filter,
    # which suppresses the very header we are about to write: the pairing would
    # land in the .ipynb and silently vanish from the .py, so pairing again
    # would look unpaired. Jupytext's own --set-formats drops the filter for
    # this reason (see jupytext/cli.py).
    if metadata.get("notebook_metadata_filter") == "-all":
        metadata.pop("notebook_metadata_filter")

    metadata["formats"] = PAIRED_FORMATS

    stem, ext = os.path.splitext(path)
    ipynb_path = path if ext == ".ipynb" else other
    py_path = path if ext == ".py" else other

    jupytext.write(nb, ipynb_path)
    jupytext.write(nb, py_path, fmt="py:percent")

    return f"Paired {ipynb_path} <-> {py_path} (formats: {PAIRED_FORMATS})"


def _import_nbclient():
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import CellExecutionError
    except ImportError:
        raise RunError(_RUN_INSTALL_HINT)
    return nbformat, NotebookClient, CellExecutionError


def discover(targets):
    """Expand files and directories into a list of notebook paths."""
    found = []
    for target in targets:
        target = Path(target)
        if target.is_dir():
            found.extend(sorted(target.rglob("*.ipynb")))
        else:
            found.append(target)
    # Checkpoint copies are Jupyter's autosave backups, not notebooks to run.
    return [p for p in found if ".ipynb_checkpoints" not in p.parts]


def run_one(path, kernel="", timeout=600, allow_errors=False, in_place=True):
    """
    Execute one notebook, saving its outputs back in place.

    Returns True if every cell ran clean. On a failing cell the notebook is
    still written (when in_place), so the traceback is visible in the notebook
    the way it would be in the browser -- nbclient's own CLI discards it.
    """
    nbformat, NotebookClient, CellExecutionError = _import_nbclient()

    if not path.is_file():
        raise RunError(f"No such notebook: {path}")

    nb = nbformat.read(path, as_version=4)

    # %%extract builds its "# Source:" header from this. ipynbname cannot
    # resolve the path without a running Jupyter server, so hand it over.
    # Relative to the invocation cwd, matching how headers read in the browser.
    try:
        source_path = os.path.relpath(path)
    except ValueError:  # different drive on Windows
        source_path = str(path.resolve())
    os.environ[NB_PATH_ENV_VAR] = source_path

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name=kernel,
        allow_errors=allow_errors,
        # Cell working dir = the notebook's own folder, so relative paths
        # inside the notebook behave like they do interactively.
        resources={"metadata": {"path": str(path.parent)}},
    )

    try:
        client.execute()
    except CellExecutionError as exc:
        print(f"FAIL  {path}\n      {exc}", file=sys.stderr)
        if in_place:
            nbformat.write(nb, path)
        return False

    if in_place:
        nbformat.write(nb, path)

    # allow_errors keeps execution going past a failure; the run still failed.
    errored = [
        index
        for index, cell in enumerate(nb.cells)
        if any(out.get("output_type") == "error" for out in cell.get("outputs", []))
    ]
    if errored:
        cells = ", ".join(str(i) for i in errored)
        print(f"FAIL  {path}\n      errors in cell(s): {cells}", file=sys.stderr)
        return False

    print(f"ok    {path}")
    return True


def run(targets, kernel="", timeout=600, allow_errors=False, in_place=True):
    """Execute every notebook in `targets`. Returns the number that failed."""
    notebooks = discover(targets)
    if not notebooks:
        raise RunError("No notebooks found.")

    results = [
        run_one(
            notebook,
            kernel=kernel,
            timeout=timeout,
            allow_errors=allow_errors,
            in_place=in_place,
        )
        for notebook in notebooks
    ]

    failed = results.count(False)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return failed


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="jlx",
        description="Tooling for jupyter_lab_extractor notebooks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pair_parser = subparsers.add_parser(
        "pair",
        help="Establish a Jupytext ipynb/py:percent pairing if none exists.",
        description=(
            "Establish a Jupytext ipynb/py:percent pairing for NOTEBOOK. Does "
            "nothing if a pairing is already established. Refuses when both "
            "halves exist unpaired."
        ),
    )
    pair_parser.add_argument(
        "notebook",
        help="Either half of the pair: the .ipynb or the .py.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Execute notebooks headlessly, saving outputs back in place.",
        description=(
            "Execute notebooks the way running them in the browser would: "
            "%%extract fires, plots and other cell outputs are produced and "
            "saved back into the .ipynb, and the first error stops the run."
        ),
    )
    run_parser.add_argument(
        "targets",
        nargs="+",
        help="Notebook files and/or directories to search for .ipynb files.",
    )
    run_parser.add_argument(
        "--kernel",
        default="",
        help="Kernel to execute with. Default: the notebook's own kernelspec.",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-cell timeout in seconds. Default: 600.",
    )
    run_parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Keep going past failing cells (the run still reports failure).",
    )
    run_parser.add_argument(
        "--check",
        action="store_true",
        help="Execute but do not write outputs back (CI mode).",
    )

    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    if args.command == "pair":
        try:
            print(pair(args.notebook))
        except PairError as exc:
            print(f"jlx: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.command == "run":
        try:
            failed = run(
                args.targets,
                kernel=args.kernel,
                timeout=args.timeout,
                allow_errors=args.allow_errors,
                in_place=not args.check,
            )
        except RunError as exc:
            print(f"jlx: {exc}", file=sys.stderr)
            return 1
        return 1 if failed else 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
