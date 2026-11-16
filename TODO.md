# TODO

Open bugs and planned work. Dated, newest last. Work lands on `dev` first (see CLAUDE.md, "Releases and branches").

## Bug (found 2026-11-14): `jlx pair` says "Already paired" and creates nothing when the other half is missing

Found while using jupyter_lab_extractor v0.1.0 in the ML_DL_for_Eng_Learn project. Still present on `dev` (0.2.0.dev1, `cli.py`).

### Symptom

```text
$ uv run jlx pair notebooks/part00_orientation/00_ml_is_engineering.py
Already paired, nothing to do: notebooks/part00_orientation/00_ml_is_engineering.py
$ uv run jlx run notebooks/part00_orientation/00_ml_is_engineering.ipynb
No such notebook: ...
```

No `.ipynb` is created, so the next step (`jlx run`) fails.

### Cause

`pair()` returns early when `is_paired(path)` is True, and `is_paired()` never checks that `counterpart(path)` exists on disk.
Two ways it returns True with the other half missing:

1. **Config-declared pairing (the case actually hit).** `is_paired()` falls through to `_config_declares_pairing(path)`, which is True as soon as
   `find_jupytext_configuration_file()` finds a `jupytext.toml` (or a `pyproject.toml` with `[tool.jupytext]`) in scope.
   A new `.py` in such a project therefore always reads as "paired", even though its `.ipynb` was never created.
2. **Metadata-declared pairing** (already noted in CLAUDE.md, "Known issue"). The file's own jupytext metadata has `formats: ipynb,py:percent`,
   but the twin is not on disk, for example after copying one half out of a paired repo.

### Reproduce

```bash
mkdir /tmp/jlx_pair_bug && cd /tmp/jlx_pair_bug
printf 'formats = "ipynb,py:percent"\n' > jupytext.toml
printf '# %%%%\nprint("hi")\n' > demo.py
jlx pair demo.py      # prints "Already paired, nothing to do"
ls                    # no demo.ipynb
```

### Suggested fix

- In `pair()`, decide on "nothing to do" only when **both halves exist**. If the declared pairing is there but `counterpart(path)` is missing, create it:
  `jupytext --sync` semantics (or `jupytext.write` of the read notebook to the other format), then report "Created <other> (pairing declared by <config file | metadata>)".
- Keep the existing refusal when both halves exist but are not paired.
- Possibly let `is_paired()` stay a pure "is a pairing declared" check, and add a separate "is the pair complete on disk" check that `pair()` uses.

### Tests to add (`tests/`)

- jupytext.toml in scope, only `x.py` on disk → `jlx pair x.py` creates `x.ipynb`, exit code 0.
- Same with only `x.ipynb` on disk → creates `x.py`.
- Metadata `formats` set, twin missing → creates the twin.
- Both halves present and paired → still "Already paired, nothing to do".
- Both halves present, not paired → still `PairError`.

### Workaround used meanwhile

In projects with a `jupytext.toml`, create the twin with `uv run jupytext --sync file.py`; `jlx run` works normally afterwards.
