# Notebooks

Executed examples of Dipolar Studio's Python API (`dipolar_app.api.Studio`). Each drives the same
registry operations the browser app uses, and checks its own results; they are shown here with
their outputs.

| Notebook | What it does |
|---|---|
| [1. A first fit](01-synthetic-biphenyl.ipynb) | The bundled synthetic biphenyl (known answer φ = 37°): preview, landscape, a fit with profile intervals, the report |
| [2. Your own data](02-your-own-data.ipynb) | An XYZ geometry and a couplings CSV: reconcile, confirm the mapping, declare the torsion, choose the model, fit |
| [3. Reproducing biphenyl in 8CB](03-reproduce-8cb.ipynb) | Experimental couplings from Di Pietro (2013), Table 3.1, **transcribed by you** (Dipolar Studio does not ship them): the four-site jump fit, compared with the reference values |

**Running them:** install Dipolar Studio and Jupyter, then open a notebook from this directory
(notebook 2 reads the tutorial files from `datasets/biphenyl-synthetic/`, by a relative path).
For notebook 3, first write your transcription as described in it, and point `COUPLINGS_CSV`
(or the `DIPOLAR_8CB_CSV` environment variable) to the file.

**For developers:** the notebooks are generated from `tools/notebooks/build.py`;
`uv run python tools/notebooks/run.py --write` rebuilds and executes them, and CI runs
`--check` (the committed notebooks match `build.py` and still run; notebook 3 runs on the
repository's validation copy of the data, and is skipped if that copy is removed).
