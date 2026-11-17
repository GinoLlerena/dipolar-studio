"""The user notebooks (beta step B3), as code: `tools/notebooks/run.py` builds them from here,
executes them, and writes `docs/notebooks/*.ipynb` with their outputs; `run.py --check` (CI)
fails if a committed notebook's cells differ from these or if one no longer runs.

Every notebook drives Dipolar Studio through its Python API (`dipolar_app.api.Studio`), the same
registry operations the browser app uses, and checks its own results with `assert`.
"""

from __future__ import annotations

from typing import Final

import nbformat
from nbformat.notebooknode import NotebookNode

KERNEL: Final = {"display_name": "Python 3", "language": "python", "name": "python3"}


def _notebook(cells: list[tuple[str, str]]) -> NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": KERNEL, "language_info": {"name": "python"}}
    nb.cells = [
        nbformat.v4.new_markdown_cell(text.strip()) if kind == "md" else nbformat.v4.new_code_cell(text.strip())
        for kind, text in cells
    ]
    for i, cell in enumerate(nb.cells):  # stable ids, so a rebuild changes nothing
        cell["id"] = f"cell-{i:02d}"
    return nb


SYNTHETIC = _notebook(
    [
        (
            "md",
            """
# 1. A first fit: the synthetic biphenyl

The bundled example is **synthetic, with a known answer**: 14 dipolar couplings of biphenyl
computed at the inter-ring torsion **φ = 37°** (rigid model, D2 symmetry), with noise of
σ = 0.5 Hz. A fit should find φ within a few standard errors of 37°. Its 68.3 % interval covers
the true value in about 68 % of noise realizations (the coverage Dipolar Studio was calibrated
on), so this fixed realization may or may not.

Everything below goes through `Studio`, the Python API of Dipolar Studio: each `call` is one
registry operation, the same the browser app sends.
""",
        ),
        (
            "code",
            """
from dipolar_app.api import Studio

studio = Studio.local()  # a session in this process (give it a directory to keep the project)
opened = studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
project = studio.call("project.describe")
print(project["name"], "-", len(project["couplings"]), "couplings,", len(project["spins"]), "protons")
print("model:", project["model"]["kind"], "on", [d["value"] for d in project["model"]["phi_domain"]], "deg")
""",
        ),
        (
            "md",
            """
## Preview: the residuals at a chosen torsion

`fit.preview` re-solves the order parameters at a fixed φ: nothing is recorded. The landscape
samples it over the torsion domain; its lowest sample is near the answer.
""",
        ),
        (
            "code",
            """
preview = studio.call("fit.preview", phi={"value": 37.0, "unit": "deg"})
print(f"at phi = 37 deg: chi2 = {preview['chi2']:.3f}")
landscape = studio.call("fit.landscape")
lowest = min((c, p) for c, p in zip(landscape["chi2"], landscape["phi"]) if c is not None)
print(f"landscape: {len(landscape['phi'])} samples, lowest chi2 = {lowest[0]:.3f} at phi = {lowest[1]:.1f} deg")
""",
        ),
        (
            "md",
            """
## The fit, with profile intervals

`studio.fit()` submits `fit.run` as a job, waits for it and returns the run's result.
""",
        ),
        (
            "code",
            """
run = studio.fit(intervals=True)
theta = {t["name"]: t["value"] for t in run["theta"]}
order = {o["name"]: o["value"] for o in run["order"]}
se = {s["name"]: s["value"] for s in run["stderr"]}
print(f"phi   = {theta['phi_deg']:.4f} +/- {se['phi_deg']:.4f} deg")
print(f"S_zz  = {order['Szz']:.5f} +/- {se['Szz']:.5f}")
print(f"Delta = {order['Delta']:.5f} +/- {se['Delta']:.5f}")
print(f"chi2 = {run['chi2']:.2f} with nu = {run['nu']}, p = {run['p_value']:.3f}; adequate: {run['adequate']}")
for i in run["intervals"]:
    print(f"  {i['parameter']:8} [{i['lower']:.4f}, {i['upper']:.4f}]  supported: {i['supported']}")
""",
        ),
        (
            "code",
            """
# The known answer: within three standard errors of phi = 37 deg.
phi_interval = next(i for i in run["intervals"] if i["parameter"] == "phi_deg")
deviation = (theta["phi_deg"] - 37.0) / se["phi_deg"]
print(f"phi - 37 deg = {deviation:+.2f} standard errors; the 68.3 % interval covers 37 deg:",
      phi_interval["lower"] < 37.0 < phi_interval["upper"])
assert run["validity"]["converged"] and run["validity"]["regular"] and run["adequate"]
assert phi_interval["supported"] and abs(deviation) < 3
""",
        ),
        (
            "md",
            """
## The report

`run.report` gives the fit as a self-contained HTML page and a CSV of the couplings. Save them
to keep or share the result.
""",
        ),
        (
            "code",
            """
run_id = studio.call("render.describe_view")["run"]["run_id"]
report = studio.call("run.report", run_id=run_id)
couplings_in_csv = len(report["csv"].splitlines()) - 1
print(report["filename"], "-", len(report["html"]), "bytes of HTML,", couplings_in_csv, "couplings in the CSV")
print(report["csv"].splitlines()[0])
studio.close()
""",
        ),
    ]
)

OWN_DATA = _notebook(
    [
        (
            "md",
            """
# 2. Your own data: an XYZ geometry and a couplings file

Your molecule enters as an **XYZ file** (element and x, y, z in Å per atom) and your
measurements as a **CSV** (`spin_a, spin_b, D_obs_Hz, sigma_Hz`); see the
[file formats](../user/file-formats.md). This notebook uses the repository's tutorial files,
the synthetic biphenyl again, so that the answer is known (φ = 37°); replace the two paths with
your own files.

The steps are those of the app's Data tab: import the geometry, reconcile the couplings with it
and **confirm the mapping** of your labels to its protons, declare the torsion, choose the model,
fit.
""",
        ),
        (
            "code",
            """
from pathlib import Path

from dipolar_app.api import Studio

DATA = Path("../../datasets/biphenyl-synthetic")
XYZ_FILE = DATA / "biphenyl.xyz"  # your geometry
CSV_FILE = DATA / "tutorial-couplings.csv"  # your couplings

studio = Studio.local()
xyz = XYZ_FILE.read_text(encoding="utf-8")
studio.call("project.import_xyz", xyz=xyz, name=XYZ_FILE.stem, expected_science_revision=0)
spins = studio.call("project.describe")["spins"]
print(len(spins), "protons, named by atom number:", ", ".join(s["label"] for s in spins))
""",
        ),
        (
            "md",
            """
## Reconcile, and confirm the mapping

Your file's labels (here `H2` … `H6'`) are not the imported protons' names (`H13` … `H22`).
`couplings.reconcile` proposes only exact matches and lists the rest; **you** decide the
mapping. Here the XYZ file's comment line names its atoms, which gives the mapping.
""",
        ),
        (
            "code",
            """
csv_text = CSV_FILE.read_text(encoding="utf-8")
proposal = studio.call("couplings.reconcile", csv=csv_text)
print("labels to map:", proposal["unmatched_labels"])

atom_names = xyz.splitlines()[1].split("atoms:")[1].split()  # from the comment line of this file
spin_of_atom = {s["atom"]: s["id"] for s in spins}
mapping = {label: spin_of_atom[atom_names.index(label)] for label in proposal["unmatched_labels"]}
diff = studio.call("couplings.reconcile", csv=csv_text, mapping=mapping)
assert diff["complete"], diff["unresolved_pairs"]
print(f"the import adds {len(diff['added'])} couplings")
imported = studio.call(
    "couplings.import", csv=csv_text, confirmed_mapping=mapping, expected_science_revision=diff["science_revision"]
)
print("imported", imported["n_couplings"], "couplings; ready to fit:", imported["ready_to_fit"])
print("  ", imported["not_ready_reason"])
""",
        ),
        (
            "md",
            """
## The torsion and the model

The fitted torsion is the dihedral of four atoms, counted from 0 in the XYZ file: here
C2–C1–C1′–C2′ (atoms 1, 0, 6, 7). For imported geometry the model is rigid, with the c2z (or
c1) order model in the input frame; the domain [−90°, 0°] holds the answer, −37° in this
dihedral's sign convention.
""",
        ),
        (
            "code",
            """
studio.call("molecule.set_torsion", torsion=[1, 0, 6, 7], expected_science_revision=studio.science_revision)
studio.call(
    "model.set",
    kind="rigid",
    order="c2z",
    frame="input",
    phi_domain=[{"value": -90, "unit": "deg"}, {"value": 0, "unit": "deg"}],
    expected_science_revision=studio.science_revision,
)
project = studio.call("project.describe")
print("ready to fit:", project["ready_to_fit"], project["not_ready_reason"] or "")
""",
        ),
        (
            "code",
            """
run = studio.fit(intervals=True)
tau = run["theta"][0]["value"]
print(f"torsion = {tau:.3f} deg; chi2 = {run['chi2']:.2f} with nu = {run['nu']}; adequate: {run['adequate']}")
worst = max(run["couplings"], key=lambda c: abs(c["normalized_residual"]))
print(f"largest misfit: {worst['label']} at {worst['normalized_residual']:.2f} sigma")
assert abs(tau + 37.0) < 0.1  # the known answer, in this dihedral's convention
studio.close()
""",
        ),
    ]
)

REPRODUCE_8CB = _notebook(
    [
        (
            "md",
            """
# 3. Reproducing biphenyl in 8CB, from your own transcription

This notebook reproduces a fit of **experimental** couplings: biphenyl dissolved in the liquid
crystal 8CB, measured by M. E. Di Pietro (PhD thesis, Université Paris-Sud / Università della
Calabria, 2013), **Table 3.1** (open copy: <http://hdl.handle.net/10955/1001>). Dipolar Studio
does not ship these values: transcribe the 12 couplings at **T_red = 0.930** yourself into a CSV
with the columns `spin_a, spin_b, D_obs_Hz, sigma_Hz`, one row per coupling, using the thesis
label → proton pair table below. Then set `COUPLINGS_CSV` to your file and run the notebook.

The model is the **symmetric four-site jump** (±φ, 180° ± φ, equal populations) on the built-in
biphenyl template. The reference values below are the fits that Dipolar Studio's independent
reference implementation gives for these data (`datasets/biphenyl-8CB-dipietro2013/expected/`,
frozen in M0); the thesis's own analysis (AP-DPD) agrees with them to 1–2 % in the order
parameters.
""",
        ),
        (
            "code",
            """
import csv
import os
from pathlib import Path

from dipolar_app.api import Studio

COUPLINGS_CSV = Path(os.environ.get("DIPOLAR_8CB_CSV", "my-8cb-T0.930.csv"))  # your transcription

# The thesis's labels and the protons of the template (ring A: H2-H6, ring B: H2'-H6').
THESIS_LABELS = {  # Table 3.1's label: the representative pair on the template
    "D12=D34": ("H2", "H3"),
    "D13=D13'": ("H2", "H2'"),
    "D11'=D33'": ("H2", "H6"),
    "D22'=D44'": ("H3", "H5"),
    "D14=D14'=D23=D23'": ("H2", "H3'"),
    "D24=D24'": ("H3", "H3'"),
    "D12'=D34'": ("H2", "H5"),
    "D16=D35": ("H2", "H4'"),
    "D15=D36": ("H2", "H4"),
    "D26=D45": ("H3", "H4'"),
    "D25=D46": ("H3", "H4"),
    "D56": ("H4", "H4'"),
}
if not COUPLINGS_CSV.exists():
    raise SystemExit(f"Transcribe Table 3.1 at T_red = 0.930 into {COUPLINGS_CSV} first (see above).")
rows = list(csv.DictReader(COUPLINGS_CSV.open(encoding="utf-8")))
print(len(rows), "couplings read from", COUPLINGS_CSV.name)
pairs = {tuple(sorted((r["spin_a"], r["spin_b"]))) for r in rows}
assert pairs == {tuple(sorted(p)) for p in THESIS_LABELS.values()}, "one row for each of Table 3.1's 12 labels"
""",
        ),
        (
            "md",
            """
## Two fits

The thesis's σ are spectral-analysis errors, far smaller than the model's misfit, so two
configurations are fitted, as in the frozen reference:

- **unweighted**: every coupling with σ = 1 Hz, an ordinary least-squares fit (the one compared
  with the published values). With no error model behind σ, its χ², p-value and adequacy flag
  have no statistical meaning, and it reports no intervals: read its values only;
- **weighted**: the transcribed σ; the fit is then expected to be flagged **inadequate**
  (p < 0.001): the model does not explain the data within those σ.
""",
        ),
        (
            "code",
            """
REFERENCE = {  # Dipolar Studio's frozen reference fits at T_red = 0.930 (jump model)
    "unweighted": {"phi_deg": 32.932075, "Szz": 0.4307484, "Delta": 0.1852351},
    "weighted": {"phi_deg": 32.974574, "Szz": 0.4309707, "Delta": 0.1839539},
}
TOLERANCE = {"phi_deg": 1e-3, "Szz": 1e-5, "Delta": 1e-5}  # a transcription rounded as printed


def fit(sigma_of):
    table = "spin_a,spin_b,D_obs_Hz,sigma_Hz\\n" + "".join(
        f"{r['spin_a']},{r['spin_b']},{r['D_obs_Hz']},{sigma_of(r)}\\n" for r in rows
    )
    with Studio.local() as studio:
        studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
        proposal = studio.call("couplings.reconcile", csv=table)  # the template's labels match yours
        assert not proposal["unmatched_labels"], proposal["unmatched_labels"]
        studio.call("couplings.import", csv=table, confirmed_mapping=proposal["proposed_mapping"],
                    expected_science_revision=studio.science_revision)
        studio.call("model.set", kind="jump4", order="bisector-diagonal", frame="bisector",
                    phi_domain=[{"value": 0, "unit": "deg"}, {"value": 90, "unit": "deg"}],
                    expected_science_revision=studio.science_revision)
        return studio.fit()


results = {"unweighted": fit(lambda r: 1), "weighted": fit(lambda r: r["sigma_Hz"])}
for name, run in results.items():
    values = {**{t["name"]: t["value"] for t in run["theta"]}, **{o["name"]: o["value"] for o in run["order"]}}
    p = run["p_value"]
    p_text = f"p = {p:.1e}" if p > 0 else "p < 1e-300"  # chi2 in the hundred thousands: p underflows
    verdict = f"  adequate: {run['adequate']} ({p_text})" if name == "weighted" else ""
    print(f"{name:10}  phi = {values['phi_deg']:.4f} deg  S_zz = {values['Szz']:.5f}  Delta = {values['Delta']:.5f}"
          f"  RMS = {run['rms_residual']['value']:.2f} Hz{verdict}")
    for key, expected in REFERENCE[name].items():
        assert abs(values[key] - expected) <= TOLERANCE[key], (name, key, values[key], expected)
assert results["weighted"]["adequate"] is False
print("reproduced: both fits agree with the reference.")
""",
        ),
    ]
)

NOTEBOOKS: Final = {
    "01-synthetic-biphenyl.ipynb": SYNTHETIC,
    "02-your-own-data.ipynb": OWN_DATA,
    "03-reproduce-8cb.ipynb": REPRODUCE_8CB,
}
