"""M1 acceptance (step 5): every frozen gate has an engine test, and gate (c) holds on the engine.

The gates are frozen in the datasets' ``expected/spec.json`` (plan §8 M1):
- (a) noiseless recovery;
- (b) a fixed-seed regression;
- (c) interval coverage over 1000 seeds;
- (d) the forward model over all pairs;
- (e) the jump model's explicit averaging;
- the 8CB reproduction, which applies only while that third-party dataset is present.

``GATE_TESTS`` names the engine test for each gate, and the ledger test checks that each named
test exists, so a gate cannot silently lose its test. Gate (c) is measured by
``tools/coverage/engine_coverage.py``. Its 1000-seed record is committed, and the tests here
check that record and reproduce part of it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, rigid_problem
from dipolar_core.fit import fit

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "datasets" / "biphenyl-synthetic" / "expected"
DIP = ROOT / "datasets" / "biphenyl-8CB-dipietro2013" / "expected"
RECORD = ROOT / "docs" / "validation" / "data" / "m1-gate-c-engine-coverage.json"
sys.path.insert(0, str(ROOT / "tools" / "coverage"))
import engine_coverage as C  # noqa: E402

SPEC = json.loads((SYN / "spec.json").read_text())

#: The engine test of each frozen gate, as "path::test_name".
GATE_TESTS: dict[str, dict[str, list[str]]] = {
    "synthetic": {
        "a_noiseless": [
            "tests/test_m1_acceptance.py::test_gate_a_noiseless_recovery",
            "packages/dipolar-core/tests/test_core_fit.py::test_noiseless_recovery",
        ],
        "b_regression": [
            "packages/dipolar-core/tests/test_core_fit.py::test_optimum_matches_the_frozen_fixture",
            "packages/dipolar-core/tests/test_core_fit.py::test_full_jacobian_covariance",
            "packages/dipolar-core/tests/test_core_fit.py::test_profile_intervals",
            "packages/dipolar-core/tests/test_core_fit.py::test_validity_flags",
        ],
        "c_coverage": [
            "tests/test_m1_acceptance.py::test_gate_c_record_is_within_the_band",
            "tests/test_m1_acceptance.py::test_gate_c_record_reproduces",
            "tests/test_m1_acceptance.py::test_gate_c_engine_coverage",
        ],
        "d_forward": [
            "packages/dipolar-core/tests/test_core_forward_inner.py::test_forward_all_45_pairs",
            "tests/test_m1_acceptance.py::test_gate_d_reversed_pairs_and_classes",
        ],
        "e_jump": [
            "tests/test_engine_jump_reference.py::test_engine_jump_equals_the_reference_explicit_average",
            "packages/dipolar-core/tests/test_core_jump.py::test_gate_e_explicit_averaging_equals_the_relabelling_shortcut",
        ],
    },
    "8CB": {
        "unweighted": ["tests/test_engine_jump_reference.py::test_engine_reproduces_the_frozen_8cb_jump_fits"],
        "weighted": ["tests/test_engine_jump_reference.py::test_engine_reproduces_the_frozen_8cb_jump_fits"],
        "e_jump": ["tests/test_engine_jump_reference.py::test_engine_jump_equals_the_reference_explicit_average"],
    },
}


def _indices(pairs: list[list[str]]) -> tuple[tuple[int, int], ...]:
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    return tuple((index[a], index[b]) for a, b in pairs)


def test_every_frozen_gate_names_an_existing_engine_test() -> None:
    assert set(GATE_TESTS["synthetic"]) == set(SPEC["gates"])
    if (DIP / "spec.json").exists():  # the 8CB gates apply only while the dataset is present
        assert set(GATE_TESTS["8CB"]) == set(json.loads((DIP / "spec.json").read_text())["gates"])
    for gates in GATE_TESTS.values():
        for tests in gates.values():
            assert tests
            for ref in tests:
                path, name = ref.split("::")
                source = (ROOT / path).read_text()
                assert re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE), f"{ref} does not exist"


# --------------------------------------------------------------------------- gate (a)


def test_gate_a_noiseless_recovery() -> None:
    data = json.loads((SYN / "noiseless.json").read_text())
    atol = SPEC["tolerances"]["noiseless_recovery_atol"]
    result = fit(rigid_problem(_indices(data["pairs"]), np.array(data["D_Hz"]), np.array(data["sigma_Hz"])))
    truth = data["truth"]
    assert abs(result.theta[0] - truth["phi_deg"]) < atol["phi_deg"]
    assert abs(result.order[0] - truth["Szz"]) < atol["Szz"]
    assert abs(result.order[1] - truth["Delta"]) < atol["Delta"]
    assert result.chi2 < 1e-12
    np.testing.assert_allclose(result.predictions, data["D_Hz"], rtol=0, atol=1e-9)


# --------------------------------------------------------------------------- gate (c)


def _record() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(RECORD.read_text())
    return record


def test_gate_c_record_is_within_the_band() -> None:
    """The committed 1000-seed engine record passes the frozen acceptance band with every interval
    supported. Every summary field is recomputed from the per-seed intervals (round 25), and the
    record names the engine version and the inputs it was made from."""
    record, cov = _record(), SPEC["coverage"]
    truth = json.loads((SYN / "noiseless.json").read_text())["truth"]
    assert record["provenance"] == C.provenance()
    n = cov["n_seeds"]
    assert record["n_seeds"] == n == len(record["seeds"])
    assert [s["seed"] for s in record["seeds"]] == list(range(n))
    lo, hi = cov["acceptance_band"]
    for name in cov["parameters"]:
        unsupported = sum(s[name] is None for s in record["seeds"])
        assert unsupported == record["interval_not_supported"][name] == 0, name
        for s in record["seeds"]:
            lower, upper = s[name]
            assert np.isfinite([lower, upper]).all() and lower <= s["estimate"][name] <= upper, (name, s["seed"])
        hits = sum(s[name][0] <= truth[name] <= s[name][1] for s in record["seeds"])
        assert hits == record["hits"][name]
        assert record["coverage"][name] == hits / n
        assert record["within_band"][name] is (lo <= hits / n <= hi) is True, name


@pytest.mark.parametrize("seed", [0, 617])
def test_gate_c_record_reproduces(seed: int) -> None:
    """The engine reproduces the record for sample seeds (the slow test reproduces all of them)."""
    tol = SPEC["tolerances"]["regression"]
    recorded = _record()["seeds"][seed]
    again = C.seed_result(seed)
    _assert_same_seed(again, recorded, tol)


def _assert_same_seed(again: dict[str, Any], recorded: dict[str, Any], tol: dict[str, float]) -> None:
    assert again["seed"] == recorded["seed"]
    atol = {"phi_deg": tol["phi_interval_endpoint_atol_deg"], "Szz": tol["S_interval_endpoint_atol"]}
    atol["Delta"] = atol["Szz"]
    for name in C.PARAMETERS:
        assert again["estimate"][name] == pytest.approx(recorded["estimate"][name], abs=atol[name])
        assert (again[name] is None) == (recorded[name] is None)
        if recorded[name] is not None:
            np.testing.assert_allclose(again[name], recorded[name], rtol=0, atol=atol[name])


@pytest.mark.slow
def test_gate_c_engine_coverage() -> None:
    """The whole ensemble, rerun: within the band, and equal to the committed record seed by seed."""
    report = C.run(SPEC["coverage"]["n_seeds"], workers=max(1, C.default_workers()))
    assert all(report["within_band"].values()), report["coverage"]
    assert not any(report["interval_not_supported"].values())
    recorded = _record()["seeds"]
    for again, before in zip(report["seeds"], recorded, strict=True):
        _assert_same_seed(again, before, SPEC["tolerances"]["regression"])


# --------------------------------------------------------------------------- gate (d)


def test_gate_d_reversed_pairs_and_classes() -> None:
    """forward.json on the engine: reversed pairs predict the same, and each symmetry class
    predicts one value, at 0°, 37° and the 90° endpoint."""
    from dipolar_core.biphenyl import rigid_design

    fwd = json.loads((SYN / "forward.json").read_text())
    s = np.array([0.25, 0.03])
    pairs = _indices(fwd["pairs"])
    reversed_pairs = tuple((b, a) for a, b in pairs)
    classes = [_indices([m.split("-") for m in members]) for members in fwd["classes"].values()]
    assert sum(len(c) for c in classes) == len(pairs) == 45
    for phi, expected in fwd["by_phi_deg"].items():
        np.testing.assert_allclose(rigid_design(float(phi), reversed_pairs) @ s, expected, rtol=0, atol=1e-6)
        for members in classes:
            values = rigid_design(float(phi), members) @ s
            np.testing.assert_allclose(values, values[0], rtol=0, atol=1e-9)
