"""A synthetic D6h fit on the installed wheels, from outside the checkout (plan, V1.5c: "Rehearse
the actual draft's wheels with a synthetic fixed D6h fit from outside the checkout").

Run it with the Python of a clean environment where only the two wheels are installed, from a
directory outside the checkout:

    cd "$(mktemp -d)"
    <env>/bin/python -I <checkout>/tools/package/rehearse_d6h.py \\
        --guide <checkout>/docs/phase2/reproduce-benzene.md \\
        --prereg <checkout>/docs/phase2/v0.3-preregistration.json

It follows the benzene guide (steps 1 and 3) with synthetic numbers:

1. It builds the geometry from the frozen constants as the guide describes: carbons at r_e(CC),
   protons radially at r_e(CC) + r_e(CH), at the frozen ring positions, z normal to the ring,
   written at 12 decimal places.
2. It computes D12, D13 and D14 from a synthetic S_zz. It uses the scalar distance-cubed law
   with its own CODATA 2018 constants, not the engine's.
3. It starts ``dipolar serve`` on a fresh project directory. Through ``Studio.connect``, it
   imports the XYZ, declares D6h with the guide's axes, chooses the fixed model, and imports the
   couplings with the confirmed mapping. Then it runs the fit.
4. It runs the guide's ``run.get`` snippet as written, except for its two path lines. It checks
   the saved run: S_zz estimated, rank verified, within 1e-8 of the synthetic value (ledger §8).

No experimental value is used: S_zz and the couplings are synthetic.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

#: A synthetic axial order parameter: not a value from any source.
S_ZZ_SYNTHETIC = -0.0815
SIGMA_HZ = 0.02
#: CODATA 2018: μ0 (N A⁻²), ħ (J s), and the proton's angular gyromagnetic ratio (rad s⁻¹ T⁻¹).
MU0 = 1.25663706212e-6
HBAR = 1.054571817e-34
GAMMA_H = 2.6752218744e8
#: The guide's axes, as rows in the input coordinates: z′ normal to the ring, x′ through H1.
AXES = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
FIXED_MODEL = {"kind": "fixed", "order": "point-group", "frame": "symmetry"}
TOLERANCE = 1e-8


def geometry(prereg: dict[str, Any], *, decimals: int) -> tuple[list[str], list[tuple[float, float, float]]]:
    """Six carbons, then H1–H6, each at its frozen ring angle, rounded to ``decimals``."""
    g, angles = prereg["geometry"], prereg["datasets"]["benzene-taggar2006"]["ring_positions"]
    r_c, r_h = g["r_cc_angstrom"], g["r_cc_angstrom"] + g["r_ch_angstrom"]
    rows = []
    for radius in (r_c, r_h):
        for name in ("H1", "H2", "H3", "H4", "H5", "H6"):
            a = math.radians(angles[name])
            rows.append((round(radius * math.cos(a), decimals) + 0.0, round(radius * math.sin(a), decimals) + 0.0, 0.0))
    return ["C"] * 6 + ["H"] * 6, rows


def xyz_text(elements: list[str], rows: list[tuple[float, float, float]], *, decimals: int) -> str:
    lines = [str(len(elements)), "synthetic benzene (V1.5c rehearsal)"]
    lines += [
        f"{e} {x:.{decimals}f} {y:.{decimals}f} {z:.{decimals}f}" for e, (x, y, z) in zip(elements, rows, strict=True)
    ]
    return "\n".join(lines) + "\n"


def couplings(prereg: dict[str, Any], rows: list[tuple[float, float, float]]) -> dict[str, float]:
    """D = K·P2(cos θ)·S_zz / r³ per orbit. Every pair lies in the ring plane, so P2 = −1/2."""
    k = -(MU0 / (4 * math.pi)) * GAMMA_H**2 * HBAR / (2 * math.pi) * 1e30  # Hz Å³
    index = {f"H{n}": 6 + n - 1 for n in range(1, 7)}
    out = {}
    for orbit, (a, b) in prereg["datasets"]["benzene-taggar2006"]["orbits"].items():
        r = math.dist(rows[index[a]], rows[index[b]])
        out[orbit] = k * (-0.5) * S_ZZ_SYNTHETIC / r**3
    return out


def matches(reference: float, estimate: float) -> bool:
    """The ledger's rule at 12 or more decimal places: 1e-8 absolute."""
    return abs(estimate - reference) <= TOLERANCE


def the_guides_snippet(guide: Path, project_dir: Path, out: Path, *, run_id: str | None = None) -> str:
    """The guide's ``run.get`` code block, with its path lines pointed at this rehearsal and, when
    given, its ``RUN_ID`` line naming the run to save."""
    blocks = [
        b for b in re.findall(r"```python\n(.*?)```", guide.read_text(encoding="utf-8"), re.S) if "Studio.connect" in b
    ]
    if len(blocks) != 1:
        raise SystemExit("the guide has no single run.get snippet")
    # A function, not a template: a Windows path's backslashes must not be read as escapes.
    project_line = f"PROJECT_DIR = {json.dumps(str(project_dir))}"
    code, n1 = re.subn(r'^PROJECT_DIR = "[^"]+"', lambda _: project_line, blocks[0], flags=re.M)
    out_line = f"OUT = {json.dumps(str(out))}"
    code, n2 = re.subn(r'^OUT = "[^"]+"', lambda _: out_line, code, flags=re.M)
    if (n1, n2) != (1, 1):
        raise SystemExit("the guide's snippet does not start with PROJECT_DIR and OUT")
    if run_id is not None:
        run_line = f"RUN_ID = {json.dumps(run_id)}"
        code, n3 = re.subn(r'^RUN_ID = "[^"]+"', lambda _: run_line, code, flags=re.M)
        if n3 != 1:
            raise SystemExit("the guide's snippet has no RUN_ID line")
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    ns = parser.parse_args()
    prereg = json.loads(ns.prereg.read_text(encoding="utf-8"))
    dipolar = shutil.which("dipolar", path=str(Path(sys.executable).parent)) or shutil.which("dipolar")
    if dipolar is None:
        raise SystemExit("no dipolar command next to this Python")
    version = subprocess.run([dipolar, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    print(f"ok  {version}")

    from dipolar_app.api import Studio

    elements, rows = geometry(prereg, decimals=12)
    observed = couplings(prereg, rows)
    names = sorted({h for pair in prereg["datasets"]["benzene-taggar2006"]["orbits"].values() for h in pair})
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\n" + "".join(
        f"{a},{b},{observed[o]!r},{SIGMA_HZ}\n"
        for o, (a, b) in prereg["datasets"]["benzene-taggar2006"]["orbits"].items()
    )
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "benzene-synthetic"
        ready = project / "serve.ready.json"
        server = subprocess.Popen(
            [dipolar, "serve", "--project-dir", str(project)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                if server.poll() is not None:
                    raise SystemExit("dipolar serve stopped")
                if time.monotonic() > deadline:
                    raise SystemExit("dipolar serve did not start")
                time.sleep(0.1)
            with Studio.connect(ready) as studio:
                rev = studio.science_revision
                rev = studio.call(
                    "project.import_xyz",
                    xyz=xyz_text(elements, rows, decimals=12),
                    name="synthetic benzene",
                    expected_science_revision=rev,
                )["science_revision"]
                rev = studio.call(
                    "molecule.set_symmetry",
                    symmetry={"point_group": "D6h", "axes": AXES},
                    expected_science_revision=rev,
                )["science_revision"]
                rev = studio.call("model.set", {**FIXED_MODEL, "expected_science_revision": rev})["science_revision"]
                spin_of_atom = {s["atom"]: s["id"] for s in studio.call("project.describe")["spins"]}
                mapping = {h: spin_of_atom[6 + int(h[1:]) - 1] for h in names}
                if not studio.call("couplings.reconcile", csv=csv, mapping=mapping)["complete"]:
                    raise SystemExit("the mapping is incomplete")
                studio.call("couplings.import", csv=csv, confirmed_mapping=mapping, expected_science_revision=rev)
                studio.fit()
                run_id = str(studio.call("run.list")["runs"][0]["id"])  # newest first: this fit
            print(f"ok  the fit ran through dipolar serve ({run_id})")

            saved = Path(tmp) / "run.json"
            snippet = the_guides_snippet(ns.guide, project, saved, run_id=run_id)
            done = subprocess.run([sys.executable, "-I", "-c", snippet], capture_output=True, text=True, timeout=120)
            if done.returncode != 0:
                raise SystemExit(f"the guide's run.get snippet failed:\n{done.stderr}")
            print("ok  the guide's run.get snippet ran")
            result = json.loads(saved.read_text(encoding="utf-8"))

            # Replace the couplings (σ changed), so the run is stale: the snippet must refuse it.
            changed = csv.replace(f",{SIGMA_HZ}\n", f",{2 * SIGMA_HZ}\n")
            with Studio.connect(ready) as studio:
                studio.call(
                    "couplings.import",
                    csv=changed,
                    confirmed_mapping=mapping,
                    expected_science_revision=studio.science_revision,
                )
            refused = Path(tmp) / "stale.json"
            snippet = the_guides_snippet(ns.guide, project, refused, run_id=run_id)
            done = subprocess.run([sys.executable, "-I", "-c", snippet], capture_output=True, text=True, timeout=120)
            if done.returncode == 0 or refused.exists() or "stale" not in done.stderr:
                raise SystemExit("the guide's snippet saved a stale run")
            print("ok  the guide's snippet refuses a stale run")
        finally:
            server.terminate()
            server.wait(timeout=30)

    (szz,) = [c for c in result["components"] if c["name"] == "Szz"]
    if result["provenance"]["fit_version"] != prereg["model"]["fixed_fit_version"]:
        raise SystemExit("the run is not the frozen fixed fit")
    if result["n_obs"] != 3 or not result["rank"]["verified"] or szz["status"] != "estimated":
        raise SystemExit("S_zz is not estimated with a verified rank")
    if not matches(S_ZZ_SYNTHETIC, float(szz["estimate"])):
        raise SystemExit(f"S_zz is not recovered: off by {abs(float(szz['estimate']) - S_ZZ_SYNTHETIC):.3e}")
    print(
        f"ok  synthetic D6h: S_zz recovered within {TOLERANCE:g} ({abs(float(szz['estimate']) - S_ZZ_SYNTHETIC):.1e})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
