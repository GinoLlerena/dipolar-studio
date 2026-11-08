"""Guards for the frozen expected answers (M0 step 2).

These tests do NOT test the engine (dipolar-core has no fitting code yet). They make sure that
(1) nobody edits the frozen files by hand, (2) the frozen numbers still follow from the
independent reference and the dataset files, and (3) the reference itself passes the gates it
imposes, so no gate can fail on its own fixture.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import biphenyl_reference as R
import numpy as np
import pytest

SYN = R.SYNTHETIC_DIR / "expected"
DIP = R.DIPIETRO_DIR / "expected"


def load(path: Path) -> dict:  # type: ignore[type-arg]
    return json.loads(path.read_text())


TOL = load(SYN / "spec.json")["tolerances"]["regression"]


@pytest.mark.parametrize("directory", [SYN, DIP], ids=["synthetic", "8CB"])
def test_manifest_matches(directory: Path) -> None:
    lines = (directory / "MANIFEST.sha256").read_text().split("\n")
    listed = dict(reversed(line.split("  ")) for line in lines if line)
    on_disk = {f.name for f in directory.glob("*.json")}
    assert set(listed) == on_disk, "expected/ contains files that are not in MANIFEST.sha256"
    for name, digest in listed.items():
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        assert actual == digest, f"{name} was edited without re-freezing (tools/reference/make_expected.py)"


@pytest.mark.parametrize("phi", [0.0, 12.3, 37.0, 89.0, 90.0])
def test_reference_geometry_equals_generator(phi: float) -> None:
    gen = R.GEN.proton_positions(phi, R.GEOMETRY["r_cc"], R.GEOMETRY["r_ch"], R.GEOMETRY["r_inter"])
    pos = R.positions(phi)
    for label, xyz in gen.items():
        np.testing.assert_allclose(pos[R.INDEX[label]], xyz, rtol=0, atol=1e-13)


def assert_fit_matches(actual: dict, expected: dict, *, intervals: bool) -> None:  # type: ignore[type-arg]
    assert actual["phi_deg"] == pytest.approx(expected["phi_deg"], abs=TOL["phi_atol_deg"])
    assert actual["Szz"] == pytest.approx(expected["Szz"], abs=TOL["S_atol"])
    assert actual["Delta"] == pytest.approx(expected["Delta"], abs=TOL["S_atol"])
    assert actual["objective"] == pytest.approx(expected["objective"], rel=TOL["objective_rtol"])
    np.testing.assert_allclose(
        actual["predictions_Hz"],
        expected["predictions_Hz"],
        rtol=0,
        atol=TOL["predictions_atol_Hz"],
    )
    assert actual["N"] == expected["N"] and actual["nu"] == expected["nu"]
    assert actual["validity"] == expected["validity"] | {
        "inner_condition_number": pytest.approx(expected["validity"]["inner_condition_number"], rel=1e-6)
    }
    if intervals:
        got, exp = actual["profile_intervals_68pct"], expected["profile_intervals_68pct"]
        np.testing.assert_allclose(got["phi_deg"], exp["phi_deg"], rtol=0, atol=TOL["phi_interval_endpoint_atol_deg"])
        for name in ("Szz", "Delta"):
            np.testing.assert_allclose(got[name], exp[name], rtol=0, atol=TOL["S_interval_endpoint_atol"])
        np.testing.assert_allclose(
            actual["covariance_full_jacobian"]["stderr"],
            expected["covariance_full_jacobian"]["stderr"],
            rtol=TOL["stderr_rtol"],
        )


def test_synthetic_noisy_fixture_reproduces() -> None:
    fx = load(SYN / "noisy_fixture.json")
    prob = R.Problem("rigid", [tuple(p) for p in fx["pairs"]], np.array(fx["y_Hz"]), np.array(fx["sigma_Hz"]))
    assert_fit_matches(R.fit_report(prob), fx["expected"], intervals=True)


def test_synthetic_fixture_inputs_match_csv() -> None:
    fx = load(SYN / "noisy_fixture.json")
    with (R.SYNTHETIC_DIR / "couplings.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert [[r["spin_a"], r["spin_b"]] for r in rows] == fx["pairs"]
    assert [float(r["D_obs_Hz"]) for r in rows] == fx["y_Hz"]
    assert len(rows) == 14 and sum(int(r["multiplicity"]) for r in rows) == 45


def test_reference_passes_noiseless_gate() -> None:
    nl = load(SYN / "noiseless.json")
    prob = R.Problem("rigid", [tuple(p) for p in nl["pairs"]], np.array(nl["D_Hz"]), np.array(nl["sigma_Hz"]))
    got = R.fit_report(prob, intervals=False)
    atol = load(SYN / "spec.json")["tolerances"]["noiseless_recovery_atol"]
    for name in ("phi_deg", "Szz", "Delta"):
        assert got[name] == pytest.approx(nl["expected"][name], abs=atol[name]), name
    assert got["objective"] < 1e-12


def test_sanity_bounds_against_prototype() -> None:
    proto = load(R.SYNTHETIC_DIR / "check_fit.out.json")
    exp = load(SYN / "noisy_fixture.json")["expected"]
    assert abs(exp["phi_deg"] - proto["phi_hat_deg"]) <= 0.05
    assert abs(exp["Szz"] - proto["Szz_hat"]) <= 1e-3 and abs(exp["Delta"] - proto["Delta_hat"]) <= 1e-3


def test_forward_all_pairs_reversed_and_classes() -> None:
    fw = load(SYN / "forward.json")
    pairs = [tuple(p) for p in fw["pairs"]]
    assert len(pairs) == 45
    s = np.array([0.25, 0.03])
    for phi, frozen in fw["by_phi_deg"].items():
        d = R.design_rigid(float(phi), pairs) @ s
        np.testing.assert_allclose(d, frozen, rtol=0, atol=TOL["predictions_atol_Hz"])
        rev = R.design_rigid(float(phi), [(b, a) for a, b in pairs]) @ s
        np.testing.assert_allclose(rev, d, rtol=0, atol=1e-9)
        value = dict(zip(["-".join(p) for p in pairs], d, strict=True))
        for members in fw["classes"].values():  # symmetry classes hold at every phi, incl. 0 and 90
            np.testing.assert_allclose([value[m] for m in members], value[members[0]], rtol=0, atol=1e-9)


def test_coverage_reference_within_band() -> None:
    cov = load(SYN / "coverage_reference.json")
    spec = load(SYN / "spec.json")["coverage"]
    assert cov["n_seeds"] == spec["n_seeds"] == 1000
    lo, hi = spec["acceptance_band"]
    for name in spec["parameters"]:
        assert lo <= cov["coverage"][name] <= hi, name


@pytest.mark.parametrize("t", ["0.930", "0.980"])
def test_8cb_reproduces(t: str) -> None:
    fx = load(DIP / f"T{t}.json")
    pairs = [tuple(p) for p in fx["pairs"]]
    y, sigma = np.array(fx["y_Hz"]), np.array(fx["sigma_Hz"])
    assert_fit_matches(
        R.fit_report(R.Problem("jump4", pairs, y, None), intervals=False),
        fx["expected"]["unweighted"],
        intervals=False,
    )
    assert fx["expected"]["unweighted"]["rms_Hz"] == pytest.approx(
        R.fit_report(R.Problem("jump4", pairs, y, None), intervals=False)["rms_Hz"], abs=1e-6
    )
    weighted = R.fit_report(R.Problem("jump4", pairs, y, sigma), intervals=False)
    assert_fit_matches(weighted, fx["expected"]["weighted"], intervals=False)
    assert fx["expected"]["weighted"]["adequate"] is False


@pytest.mark.parametrize("t", ["0.930", "0.980"])
def test_8cb_inputs_match_csv(t: str) -> None:
    fx = load(DIP / f"T{t}.json")
    with (R.DIPIETRO_DIR / "couplings.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if r["T_red"] == t]
    assert [[r["spin_a"], r["spin_b"]] for r in rows] == fx["pairs"]
    assert [float(r["D_obs_Hz"]) for r in rows] == fx["y_Hz"]
    assert [float(r["sigma_Hz"]) for r in rows] == fx["sigma_Hz"]


@pytest.mark.parametrize("phi", [1.0, 17.5, 33.0, 60.0, 89.0])
def test_jump_explicit_equals_shortcut(phi: float) -> None:
    fx = load(DIP / "T0.930.json")
    pairs = [tuple(p) for p in fx["pairs"]]
    np.testing.assert_allclose(
        R.design_jump_explicit(phi, pairs), R.design_jump_shortcut(phi, pairs), rtol=0, atol=1e-9
    )
