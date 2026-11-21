# Getting started with Dipolar Studio (beta)

Dipolar Studio fits the **conformation** (the inter-ring torsion φ) and the **orientational
order** (the Saupe order matrix) of a biphenyl-type molecule dissolved in a liquid crystal, from
its NMR **dipolar couplings**. It runs on your computer: a local server, `dipolar serve`, and the
app in your browser. Nothing is sent anywhere else.

This is a **beta**. What it covers, and what it does not, is listed under
[Scope of the beta](#scope-of-the-beta). Please report problems (see [Reporting a
problem](#reporting-a-problem)).

## Install

You need **Python 3.12 or newer**. A virtual environment keeps the installation separate:

```bash
python3 -m venv dipolar-env
source dipolar-env/bin/activate        # Windows: dipolar-env\Scripts\activate
```

Then install the two wheels of the release (the browser app is bundled inside them; no Node is
needed):

```bash
pip install dipolar_core-0.1.0b1-py3-none-any.whl dipolar_app-0.1.0b1-py3-none-any.whl
dipolar --version
```

`dipolar --version` prints the versions of both packages and of the tool contract; please include
it in any report.

**From the source repository** instead (needs [uv](https://docs.astral.sh/uv/), Node 22 and
pnpm 9): `tools/package/build.sh` builds the same wheels into `dist/packages/`.

## Start the app

Choose a directory for your project (it holds the project's history: every change is recorded
there, and the app resumes from it), then:

```bash
dipolar serve --project-dir ~/dipolar/my-project --open
```

Your browser opens the app. The server listens only on `127.0.0.1`, at a port the system
chooses; the link it opens signs that browser tab in once. To open the app again in another tab
while the server runs:

```bash
dipolar open --project-dir ~/dipolar/my-project
```

Stop the server with **Ctrl+C**. Starting it again on the same directory brings back the project
as you left it. One server at a time can use a project directory.

## A first fit (the synthetic example)

The app has four workspaces, as tabs: **Data**, **Fit**, **Structure** and **Proposals**.

1. **Data:** "Open the synthetic biphenyl example". It is a synthetic data set with a known
   answer: 14 couplings computed at φ = 37° with noise of σ = 0.5 Hz.
2. **Fit:** the **preview** lets you drag φ and see the residuals follow at once, with the χ²
   landscape over the torsion domain. Tick "Profile intervals (slower)" and **Run fit**. The fit
   runs as a job; when it ends, its result shows φ, the order parameters (S_zz, Δ), χ², the
   residuals and the validity flags (convergence, adequacy, identifiability, physical
   admissibility), each judged separately.
3. **Structure:** the molecule with each coupling drawn as an arc, coloured by its misfit; select
   couplings here or in any table.
4. **Data → Export** saves the project as a `.dipolar.json` file, which **Load a project file…**
   reads back.

Changes to the science (the geometry, the couplings, the torsion, the model, or another project
opened or loaded over the current one) can be undone, the **last 100** of them, with **Undo** and
**Redo** in the title bar. Opening the first project, the view (selection, camera, layers) and
fits are not undone. A fit made before a change is marked **stale** until the data are as they
were.

## Reports

A fit's panel in the **Fit** tab has **Download report** (an HTML page to keep, print or send:
the result, its validity flags and intervals, the model, every coupling's residual, and where the
numbers came from: the fit's inputs, the software and its numerical settings) and **Couplings
CSV** (the same couplings table at full precision, for a spreadsheet or a script). With the same
version of Dipolar Studio, the same fit always gives the same report (a newer version may word it
differently; the report names the version), and the report describes that fit, whatever has
changed in the project since. From Python: `studio.call("run.report", run_id=...)` returns both, as `html` and
`csv`.

## Your own data

Two kinds of input, both described in [file formats](file-formats.md):

- **Couplings** (CSV): one row per measured dipolar coupling, with its uncertainty σ.
- **Geometry**: either the built-in **biphenyl template** (open the example, then import your
  couplings over it), or your own coordinates as an **XYZ file** ("Import XYZ geometry…").

Importing couplings goes through a **reconciliation** step: the app proposes how the labels in
your file map to the molecule's protons and shows what would change. Nothing is applied until you
confirm the mapping.

For **imported geometry**, also declare the torsion to fit: four atom indices (a, i, j, b), where
i–j is the rotating bond and a, b are neighbours on each side. Then choose the model:

| Geometry | Models |
|---|---|
| The biphenyl template | **rigid** (φ in [0°, 90°] or [0°, 180°]); the symmetric **four-site jump** (±φ, 180° ± φ, equal populations; φ in [0°, 90°]) |
| Imported XYZ | **rigid**, order model **c2z** or **c1**, in the input frame |

Under the model, the Data tab says when the project is **ready to fit**, and what is missing if
it is not.

### A rigid molecule (fixed geometry; after 0.1)

The development version also fits a **rigid molecule with no torsion**, such as benzene or a
dichlorobenzene, from its XYZ file. Only the order tensor is fitted, so the fit is linear and its
intervals are exact. The worked example is synthetic 1,4-dichlorobenzene
(`datasets/dichlorobenzene-synthetic/`, with the expected answer in its README):

1. **Import the geometry** ("Import XYZ geometry…").
2. **Declare its symmetry** in the Data tab's Symmetry form: the point group (C1, Cs, C2v, D2h, D3h
   or D6h), its axes x′, y′, z′ as rows in your file's coordinates, and the matching tolerance. The
   declaration is checked against every atom; a refusal says what does not match. If every proton
   lies in one plane and no group beyond C1 is declared, the form **suggests Cs** with that plane as
   the mirror. It is only a suggestion. Declaring Cs makes the plane a mirror of the molecule
   (the geometry is symmetrized onto it) and reduces the model to the in-plane block of the order
   tensor; which combinations of that block your couplings determine is what the fit reports. (An
   exactly planar molecule fitted as C1 cannot have its rank verified: its out-of-plane
   components are not determined.)
3. **Choose the model** "Fixed geometry (no torsion)" and apply it. It has no φ domain.
4. **Import the couplings**, one row per observed pair orbit: a symmetry copy is not a new
   observation (see [file formats](file-formats.md)).
5. **Run the fit.** The Fit tab shows the **estimable combinations** of the order tensor (each with
   its estimate, standard error and exact 68.3 % and 95 % intervals), the components fixed by
   symmetry, the rank, the adequacy and the admissibility, and what the results assume. There is
   no torsion, so no preview slider and no χ²(φ) landscape.
6. The **Structure** tab looks along the declared symmetry axis on which the molecule is least
   spread out, so a ring is seen face-on when one of the declared axes is normal to its plane. It
   draws the axes x′, y′, z′ and the pairs of each observed orbit: at most 2000 arcs, plus up to
   2000 more for the symmetry copies of the selected and highlighted couplings. The view says how
   many copies it leaves out.

Isotopes (¹³C, ¹⁵N, D) are declared with the operation `molecule.set_isotope` (Python or HTTP);
the page shows them in the atom table.

## Using Python

Every action in the app is an **operation** of one registry, and the same operations are
available from Python, without the browser:

```python
from dipolar_app.api import Studio

with Studio.local() as studio:                      # a session in this process
    studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
    run = studio.fit(intervals=True)                # fit.run, wait for the job, run.get
    print(run["theta"], run["order"], run["chi2"])
```

- `Studio.local(project_dir)` keeps the project's history in `project_dir`, like `dipolar serve`.
- `Studio.connect(".../serve.ready.json")` drives a **running** `dipolar serve`: the browser shows
  what your script does.
- `studio.call(name, ...)` returns the operation's result; a refused operation raises
  `OperationFailed` with the server's code, message and hint. Over HTTP, a reply that is not an
  operation's at all (a proxy's error page, say) raises it with the code `NOT_AN_ENVELOPE` and the
  reply's `http_status`.
- A local `Studio` serves one call at a time, and closing it waits for a call in progress
  (`studio.fit()` waits for its job in slices of up to 25 s).

Executed examples: the [notebooks](../notebooks/README.md) (a first fit, your own data, and
reproducing biphenyl in 8CB from your own transcription of the published couplings).

The operations, with their arguments and results, are listed in
`packages/dipolar-app/registry.snapshot.json` in the repository, and by `GET /api/v1/registry` on
a running server (with a token from its ready file).

## Scope of the beta

- **Molecules:** biphenyl-type, two rings and one inter-ring torsion; the template or your XYZ.
- **Models:** rigid and the symmetric four-site jump (template); rigid with c2z or c1 order
  (imported geometry). Other molecule classes and models are Phase 2 work.
- **Observables:** ¹H–¹H dipolar couplings D, in Hz, with σ.
- **Results:** the fitted torsion and order parameters, χ², residuals, validity flags, and
  profile intervals where the fit supports them.
- **Known limits:** very large projects (tens of thousands of couplings) are slow to preview; the
  structure view renders SVG only.

## Reporting a problem

Please open an issue at <https://github.com/GinoLlerena/dipolar-studio/issues> with:

- what you did, what you expected and what happened;
- the output of `dipolar --version`;
- if you can, the exported project (`.dipolar.json`) and your input files.

## Credits

Dipolar Studio rescues the 1998 graduation thesis of **Gino Llerena and Marco Idrogo**, advised by
**Dr. Jaime Avalos**. The new implementation (2026) is by Gino Llerena, with AI assistance.
