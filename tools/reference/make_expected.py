"""Write (freeze) the expected answers in datasets/*/expected/ from the independent reference.

    uv run python -I tools/reference/make_expected.py            # fixtures + coverage (~2 min)

Re-freezing is a deliberate act: any change to a frozen file must be explained in
docs/adr/0003-scientific-inference-contract.md (changelog) and reviewed. The fixture tests
re-run this reference and fail if the frozen numbers drift beyond the stated tolerances, and
MANIFEST.sha256 detects edits by hand.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import biphenyl_reference as R

FROZEN_ON = "2026-11-07"
REFERENCE = "tools/reference/biphenyl_reference.py (NumPy/SciPy; independent of dipolar-core)"
COVERAGE = {
    "n_seeds": 1000,
    "seed_rule": "numpy.random.default_rng(numpy.random.SeedSequence(19980101, spawn_key=(k,))) for k in 0..999",
    "noise": (
        "y_k = noiseless predictions of the 14 unique couplings + rng.normal(0, 0.5, size=14), "
        "in couplings.csv row order"
    ),
    "interval": "profile interval at raw delta chi2 = 1.00, one parameter at a time, other parameters re-minimised",
    "parameters": ["phi_deg", "Szz", "Delta"],
    "nominal": 0.683,
    "acceptance_band": [0.645, 0.721],
    "band_note": "about a 99% binomial band for n = 1000 at p = 0.683",
}
TOLERANCES = {
    "regression": {
        "predictions_atol_Hz": 1e-6,
        "phi_atol_deg": 1e-4,
        "S_atol": 1e-6,
        "objective_rtol": 1e-6,
        "phi_interval_endpoint_atol_deg": 1e-4,
        "S_interval_endpoint_atol": 1e-6,
        "stderr_rtol": 1e-3,
    },
    "noiseless_recovery_atol": {"phi_deg": 1e-8, "Szz": 1e-8, "Delta": 1e-8},
    "sanity_bounds_vs_check_fit_out": {
        "phi_deg": 0.05,
        "S": 0.001,
        "note": "rounded prototype values are sanity bounds only",
    },
    "note": "plan v0.6 §8 M1; objective, interval and stderr tolerances added at the M0 freeze",
}
OPTIMUM = (
    "refined bounded optimum: best point of the grid 0:0.5:90 deg, refined by bounded 1-D "
    "minimisation of the VarPro profile objective over the neighbouring grid cells "
    "(xatol 1e-11 deg); the grid point itself is NOT the expected value"
)
FRAME = (
    "bisector frame of datasets/biphenyl-synthetic/generate.py: z along the inter-ring axis "
    "(ring A at z < 0), x bisects the two ring planes, y = z × x; the tensor is diagonal "
    "there with free Szz and Delta = Sxx − Syy"
)
ADEQUACY_POLICY = {"statistic": "p = chi2.sf(chi2, nu)", "adequate_if": "p >= 1e-3"}


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_manifest(directory: Path) -> None:
    lines = []
    for f in sorted(directory.glob("*.json")):
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}")
    (directory / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- synthetic
def synthetic(run_coverage: bool) -> None:
    out = R.SYNTHETIC_DIR / "expected"
    truth = json.loads((R.SYNTHETIC_DIR / "truth.json").read_text(encoding="utf-8"))
    rows = read_rows(R.SYNTHETIC_DIR / "couplings.csv")
    pairs = [(r["spin_a"], r["spin_b"]) for r in rows]
    sigma = np.array([float(r["sigma_Hz"]) for r in rows])
    s_true = np.array([truth["Szz"], truth["Delta"]])
    y0 = R.design_rigid(truth["phi_deg"], pairs) @ s_true

    write_json(
        out / "spec.json",
        {
            "dataset": "biphenyl-synthetic",
            "frozen_on": FROZEN_ON,
            "reference_implementation": REFERENCE,
            "model": "rigid (single conformer)",
            "estimand": "rigid effective inter-ring torsion phi",
            "frame": FRAME,
            "geometry_A": R.GEOMETRY,
            "K_HH_Hz_A3": R.K_HH,
            "phi_domain_deg": list(R.PHI_DOMAIN),
            "equivalences": (
                "At fixed labels (phi, Delta) and (-phi, Delta) are equivalent; (180 ± phi, -Delta) "
                "only together with the ring-B relabelling H2'<->H6', H3'<->H5'. Domain folded to [0, 90]."
            ),
            "N_rule": "N counts the 14 unique couplings; multiplicity (symmetry-copied) pairs never inflate N",
            "p_free": ["phi_deg", "Szz", "Delta"],
            "likelihood": "Gaussian, diagonal, known sigma = 0.5 Hz (not rescaled by chi2_nu)",
            "optimum_convention": OPTIMUM,
            "tolerances": TOLERANCES,
            "coverage": COVERAGE,
            "gates": {
                "a_noiseless": "fit noiseless.json -> recover truth within noiseless_recovery_atol; objective ~ 0",
                "b_regression": "fit couplings.csv -> match noisy_fixture.json within the regression tolerances",
                "c_coverage": "coverage over the seed ensemble within acceptance_band, for each parameter",
                "d_forward": "forward.json: all 45 pairs, reversed pairs and the 0/90 deg endpoints",
                "e_jump": "see the 8CB expected set (explicit four-conformer average == relabelling shortcut)",
            },
        },
    )
    write_json(
        out / "noiseless.json",
        {
            "description": "noiseless couplings computed in code at the truth (not the rounded CSV)",
            "truth": {"phi_deg": truth["phi_deg"], "Szz": truth["Szz"], "Delta": truth["Delta"]},
            "pairs": pairs,
            "D_Hz": y0.tolist(),
            "sigma_Hz": sigma.tolist(),
            "expected": {
                "phi_deg": truth["phi_deg"],
                "Szz": truth["Szz"],
                "Delta": truth["Delta"],
                "objective": 0.0,
            },
        },
    )

    y = np.array([float(r["D_obs_Hz"]) for r in rows])
    rep = R.fit_report(R.Problem("rigid", pairs, y, sigma))
    rep["p_value"] = float(stats.chi2.sf(rep["objective"], rep["nu"]))
    rep["adequate"] = rep["p_value"] >= 1e-3
    write_json(
        out / "noisy_fixture.json",
        {
            "description": "refined fit of couplings.csv (D_obs_Hz, sigma_Hz), rigid model, weighted",
            "pairs": pairs,
            "y_Hz": y.tolist(),
            "sigma_Hz": sigma.tolist(),
            "adequacy_policy": ADEQUACY_POLICY,
            "expected": rep,
        },
    )

    labels = sorted(R.LABELS, key=lambda s: (s.endswith("'"), s))
    all_pairs = list(combinations(labels, 2))
    forward = {
        "description": "rigid-model predictions for all 45 proton pairs at Szz = 0.25, Delta = 0.03",
        "pairs": all_pairs,
        "by_phi_deg": {},
    }
    for phi in (0.0, 37.0, 90.0):
        d = R.design_rigid(phi, all_pairs) @ s_true
        rev = R.design_rigid(phi, [(b, a) for a, b in all_pairs]) @ s_true
        assert np.array_equal(d, rev) or np.abs(d - rev).max() < 1e-9
        forward["by_phi_deg"][f"{phi:g}"] = d.tolist()
    forward["reversed_pairs"] = "D(b, a) == D(a, b) for every pair (checked at freeze, atol 1e-9 Hz)"
    forward["classes"] = {r["spin_a"] + "-" + r["spin_b"]: r["equivalent_pairs"].split() for r in rows}
    write_json(out / "forward.json", forward)

    if run_coverage:
        write_json(out / "coverage_reference.json", coverage(pairs, y0, sigma, truth))
    write_manifest(out)


def coverage(
    pairs: list[tuple[str, str]], y0: np.ndarray, sigma: np.ndarray, truth: dict[str, float]
) -> dict[str, object]:
    hits = {"phi_deg": 0, "Szz": 0, "Delta": 0}
    unsupported = {"phi_deg": 0, "Szz": 0, "Delta": 0}
    for k in range(COVERAGE["n_seeds"]):
        rng = np.random.default_rng(np.random.SeedSequence(19980101, spawn_key=(k,)))
        y = y0 + rng.normal(0.0, 0.5, size=len(y0))
        prob = R.Problem("rigid", pairs, y, sigma)
        opt = R.refine(prob)
        phi, chi2, s = float(opt["phi"]), float(opt["chi2"]), np.asarray(opt["s"])
        intervals = {
            "phi_deg": R.profile_interval_phi(prob, phi, chi2),
            "Szz": R.profile_interval_order(prob, 0, float(s[0]), phi, chi2),
            "Delta": R.profile_interval_order(prob, 1, float(s[1]), phi, chi2),
        }
        for name, (lo, hi) in intervals.items():
            if lo is None or hi is None:
                unsupported[name] += 1
            elif lo <= truth[name] <= hi:
                hits[name] += 1
    n = COVERAGE["n_seeds"]
    band = COVERAGE["acceptance_band"]
    return {
        "description": "coverage achieved by the reference implementation under spec.json 'coverage'",
        "n_seeds": n,
        "coverage": {k: v / n for k, v in hits.items()},
        "interval_not_supported": unsupported,
        "within_band": {k: band[0] <= v / n <= band[1] for k, v in hits.items()},
    }


# --------------------------------------------------------------------------- 8CB
def dipietro() -> None:
    out = R.DIPIETRO_DIR / "expected"
    rows = read_rows(R.DIPIETRO_DIR / "couplings.csv")
    proto = json.loads((R.DIPIETRO_DIR / "check_fit.out.json").read_text(encoding="utf-8"))
    write_json(
        out / "spec.json",
        {
            "dataset": "biphenyl-8CB-dipietro2013",
            "frozen_on": FROZEN_ON,
            "reference_implementation": REFERENCE,
            "model": (
                "symmetric four-site jump (+phi, -phi, 180-phi, 180+phi), equal populations, one tensor "
                "diagonal in each conformer's acute-bisector frame (shared Szz, Delta)"
            ),
            "estimand": "jump-model phi (NOT the thesis AP-DPD phi_m; a different quantity)",
            "frame": FRAME,
            "geometry_A": R.GEOMETRY,
            "geometry_note": "idealised regular rings, NOT the optimised geometry used in the thesis",
            "phi_domain_deg": list(R.PHI_DOMAIN),
            "temperatures": ["0.930", "0.980"],
            "N_rule": "12 unique couplings per temperature; p_free = 3; nu = 9",
            "configurations": {
                "unweighted": (
                    "ordinary least squares (no error model): report phi, Szz, Delta, RMS, predictions; "
                    "intervals not supported"
                ),
                "weighted": "spectral sigma as a Gaussian likelihood: report the fit AND the inadequacy flag",
            },
            "adequacy_policy": ADEQUACY_POLICY,
            "optimum_convention": OPTIMUM,
            "tolerances": TOLERANCES,
            "gates": {
                "unweighted": (
                    "reproduce phi, Szz, Delta, RMS and the prediction vector within the regression tolerances"
                ),
                "weighted": "reproduce the fit within the regression tolerances and report adequate == false",
                "e_jump": "explicit four-conformer averaging equals the relabelling shortcut (atol 1e-9 Hz)",
            },
        },
    )
    for t in ("0.930", "0.980"):
        sel = [r for r in rows if r["T_red"] == t]
        pairs = [(r["spin_a"], r["spin_b"]) for r in sel]
        y = np.array([float(r["D_obs_Hz"]) for r in sel])
        sigma = np.array([float(r["sigma_Hz"]) for r in sel])
        unweighted = R.fit_report(R.Problem("jump4", pairs, y, None), intervals=False)
        unweighted["intervals"] = "not supported: no error model"
        weighted = R.fit_report(R.Problem("jump4", pairs, y, sigma), intervals=False)
        weighted["p_value"] = float(stats.chi2.sf(weighted["objective"], weighted["nu"]))
        weighted["adequate"] = weighted["p_value"] >= 1e-3
        weighted["intervals"] = "not supported: model inadequate under the spectral-sigma likelihood"
        phi = float(unweighted["phi_deg"])  # type: ignore[arg-type]
        jump_diff = max(
            float(np.abs(R.design_jump_explicit(p, pairs) - R.design_jump_shortcut(p, pairs)).max())
            for p in (5.0, phi, 60.0, 85.0)
        )
        assert jump_diff < 1e-9, jump_diff
        ref = proto[t]
        sanity = {
            "phi_deg": abs(phi - ref["phi_deg"]),
            "Szz": abs(float(unweighted["Szz"]) - ref["Szz"]),  # type: ignore[arg-type]
            "Delta": abs(float(unweighted["Delta"]) - ref["Delta"]),
        }  # type: ignore[arg-type]
        assert sanity["phi_deg"] <= 0.05 and sanity["Szz"] <= 1e-3 and sanity["Delta"] <= 1e-3, sanity
        write_json(
            out / f"T{t}.json",
            {
                "T_red": t,
                "pairs": pairs,
                "thesis_labels": [r["thesis_label"] for r in sel],
                "y_Hz": y.tolist(),
                "sigma_Hz": sigma.tolist(),
                "expected": {"unweighted": unweighted, "weighted": weighted},
                "jump_check": {
                    "explicit_vs_shortcut_max_abs_diff_Hz": jump_diff,
                    "phi_values_checked_deg": [5.0, phi, 60.0, 85.0],
                },
                "sanity_vs_check_fit_out": sanity,
                "published_AP_DPD_for_context": ref["thesis_AP_DPD"],
            },
        )
    write_manifest(out)


if __name__ == "__main__":
    synthetic(run_coverage="--no-coverage" not in sys.argv)
    if (R.DIPIETRO_DIR / "couplings.csv").exists():  # third-party data, removable (datasets/README.md)
        dipietro()
    print("frozen:", R.SYNTHETIC_DIR / "expected", R.DIPIETRO_DIR / "expected")
