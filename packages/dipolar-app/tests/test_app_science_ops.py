"""The M2 step 1 science operations through the Python adapter (dipolar_app.science_ops).

The fits are compared with the core directly (``dipolar_core``) or with the frozen fixtures, so
the operations are tested as a faithful transport of the science, not as a second implementation.
"""

from __future__ import annotations

from itertools import combinations
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from conftest import AGENT, VIEWER, client, expected, new_session, run_fit
from dipolar_app.client import LocalClient
from dipolar_app.formats import parse_xyz
from dipolar_app.journal import Journal
from dipolar_app.reporting import ADEQUATE_P_MIN, interval_policy
from dipolar_app.science import problem_for
from dipolar_app.science_ops import ETHANE_XYZ
from dipolar_app.session import replay
from dipolar_core.biphenyl import jump_problem
from dipolar_core.torsion import TorsionGeometry, imported_problem

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}
TORSION = (2, 0, 1, 5)  # H–C–C–H of the ethane example


def deg(value: float) -> dict[str, object]:
    return {"value": value, "unit": "deg"}


def ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


def error(envelope: dict[str, Any], code: str, field: str | None = None) -> dict[str, Any]:
    assert not envelope["ok"], envelope
    assert envelope["error"]["code"] == code, envelope
    if field is not None:
        assert envelope["error"]["offending_field"] == field, envelope
    body: dict[str, Any] = envelope["error"]
    return body


def opened() -> LocalClient:
    c = client(new_session())
    ok(c.call("project.open_example", OPEN))
    return c


def named(values: list[dict[str, Any]]) -> dict[str, float]:
    return {v["name"]: v["value"] for v in values}


def model_args(kind: str, order: str, frame: str, lo: float, hi: float, revision: int) -> dict[str, object]:
    return {
        "kind": kind,
        "order": order,
        "frame": frame,
        "phi_domain": [deg(lo), deg(hi)],
        "expected_science_revision": revision,
    }


# --------------------------------------------------------------------------- describe and the model
def test_describe_reports_the_model_estimand_and_readiness() -> None:
    r = ok(opened().call("project.describe"))
    assert r["model"] == {
        "kind": "rigid",
        "order": "bisector-diagonal",
        "frame": "bisector",
        "phi_domain": [deg(0.0), deg(90.0)],
    }
    assert r["geometry"]["kind"] == "template" and r["ready_to_fit"] and r["not_ready_reason"] is None
    assert "folded to [0°, 90°]" in r["estimand"] and r["frame"].startswith("bisector frame")


def test_model_set_serves_the_jump_model_faithfully() -> None:
    c = opened()
    r = ok(c.call("model.set", model_args("jump4", "bisector-diagonal", "bisector", 0, 90, 1)))
    assert r["science_revision"] == 2 and r["ready_to_fit"]
    assert "four-site jump" in ok(c.call("project.describe"))["estimand"]
    preview = ok(c.call("fit.preview", {"phi": deg(41.0)}))
    data = expected("noisy_fixture.json")
    index = {s: i for i, s in enumerate(("H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'"))}
    pairs = tuple((index[a], index[b]) for a, b in data["pairs"])
    core = jump_problem(pairs, np.array(data["y_Hz"]), np.array(data["sigma_Hz"])).inner(np.array([41.0]))
    assert [o["name"] for o in preview["order"]] == ["Szz", "Delta"]
    np.testing.assert_allclose([o["value"] for o in preview["order"]], core.params, rtol=0, atol=1e-12)
    np.testing.assert_allclose([x["calculated"]["value"] for x in preview["couplings"]], core.predictions, atol=1e-9)
    assert preview["chi2"] == pytest.approx(core.chi2, rel=1e-12)
    assert "four-site jump" in preview["estimand"]


@pytest.mark.parametrize(
    ("args", "code", "field"),
    [
        (model_args("jump4", "c1", "bisector", 0, 90, 1), "INVALID_ARGUMENT", None),  # jump is bisector-diagonal
        (model_args("rigid", "c1", "input", 0, 90, 1), "INVALID_ARGUMENT", None),  # the template has no input frame
        (model_args("rigid", "c2z", "bisector", 0, 45, 1), "OUT_OF_DOMAIN", "phi_domain"),
        (model_args("jump4", "bisector-diagonal", "bisector", 0, 180, 1), "OUT_OF_DOMAIN", "phi_domain"),
        # The example's classes are D2 equivalences, not equivalences of C1 (round 22, finding 5).
        (model_args("rigid", "c1", "ring-a", 0, 90, 1), "INVALID_ARGUMENT", None),
        (model_args("rigid", "c1", "ring-a", 0, 180, 0), "REVISION_CONFLICT", "expected_science_revision"),
    ],
)
def test_model_set_refuses_what_the_core_cannot_fit(args: dict[str, object], code: str, field: str | None) -> None:
    c = opened()
    before = ok(c.call("project.describe"))
    error(c.call("model.set", args), code, field)
    assert ok(c.call("project.describe")) == before  # nothing changed


def without_classes(c: LocalClient, revision: int) -> int:
    """Re-import the project's couplings as plain rows (no symmetry classes); the next revision."""
    d = ok(c.call("project.describe"))
    label = {s["id"]: s["label"] for s in d["spins"]}
    rows = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"] + [
        f"{label[x['spin_a']]},{label[x['spin_b']]},{x['value']['value']!r},{x['sigma']['value']!r}"
        for x in d["couplings"]
    ]
    csv = "\n".join(rows) + "\n"
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    ok(c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": revision}))
    return revision + 1


def test_the_fixed_label_domain_reaches_obtuse_torsions() -> None:
    c = opened()
    revision = without_classes(c, 1)
    ok(c.call("model.set", model_args("rigid", "c1", "ring-a", 0, 180, revision)))
    r = ok(c.call("fit.preview", {"phi": deg(120.0)}))
    assert [o["name"] for o in r["order"]] == ["Szz", "Delta", "Sxy", "Sxz", "Syz"]
    assert "fixed ring-B labels" in r["estimand"] and r["frame"].startswith("ring-A frame")
    error(c.call("fit.preview", {"phi": deg(181.0)}), "OUT_OF_DOMAIN", "phi.value")


def test_science_mutations_need_the_apply_tier() -> None:
    session = new_session()
    ok(client(session).call("project.open_example", OPEN))
    args = model_args("jump4", "bisector-diagonal", "bisector", 0, 90, 1)
    error(client(session, VIEWER).call("model.set", args), "CAPABILITY_DENIED")
    error(client(session, AGENT).call("model.set", args), "PROPOSAL_REQUIRED")
    error(client(session, VIEWER).call("fit.run", {"expected_science_revision": 1}), "CAPABILITY_DENIED")


# --------------------------------------------------------------------------- fit.run and the interval policy
def test_fit_run_reproduces_the_frozen_fixture_with_intervals() -> None:
    e = expected("noisy_fixture.json")["expected"]
    tol = expected("spec.json")["tolerances"]["regression"]
    r = ok(run_fit(opened(), {"intervals": True}))
    assert named(r["theta"])["phi_deg"] == pytest.approx(e["phi_deg"], abs=tol["phi_atol_deg"])
    order = named(r["order"])
    assert order["Szz"] == pytest.approx(e["Szz"], abs=tol["S_atol"])
    assert order["Delta"] == pytest.approx(e["Delta"], abs=tol["S_atol"])
    assert r["chi2"] == pytest.approx(e["objective"], rel=tol["objective_rtol"])
    assert (r["n_obs"], r["p_free"], r["nu"]) == (14, 3, 11)
    assert r["adequate"] is True and r["validity"]["regular"] is True
    stderr = named(r["stderr"])
    np.testing.assert_allclose(
        [stderr[n] for n in ("phi_deg", "Szz", "Delta")],
        e["covariance_full_jacobian"]["stderr"],
        rtol=tol["stderr_rtol"],
    )
    frozen = e["profile_intervals_68pct"]
    for iv in r["intervals"]:
        assert iv["supported"], iv
        atol = (
            tol["phi_interval_endpoint_atol_deg"] if iv["parameter"] == "phi_deg" else tol["S_interval_endpoint_atol"]
        )
        np.testing.assert_allclose([iv["lower"], iv["upper"]], frozen[iv["parameter"]], rtol=0, atol=atol)
    assert [iv["parameter"] for iv in r["intervals"]] == ["phi_deg", "Szz", "Delta"]
    assert "regular optimum of an adequate fit" in r["intervals_policy"]


def test_fit_run_without_intervals_computes_none() -> None:
    r = ok(run_fit(opened()))
    assert r["intervals"] == [] and r["adequate"] is True


def test_an_inadequate_fit_reports_its_estimates_but_no_intervals() -> None:
    """Round 21, finding 3, enforced: σ ten times too small makes the fit inadequate."""
    c = opened()
    d = ok(c.call("project.describe"))
    rows = ["spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity,equivalent_pairs"]
    for x in d["couplings"]:
        a, b = (next(s["label"] for s in d["spins"] if s["id"] == i) for i in (x["spin_a"], x["spin_b"]))
        rows.append(f"{a},{b},{x['value']['value']!r},0.05,{x['multiplicity']},{' '.join(x['equivalent_pairs'])}")
    csv = "\n".join(rows) + "\n"
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    ok(c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1}))
    r = ok(run_fit(c, {"intervals": True}))
    assert r["validity"]["regular"] is True and r["p_value"] < ADEQUATE_P_MIN and r["adequate"] is False
    assert named(r["theta"])["phi_deg"] == pytest.approx(
        expected("noisy_fixture.json")["expected"]["phi_deg"], abs=1e-4
    )
    assert all(not iv["supported"] and iv["lower"] is None for iv in r["intervals"])
    assert all("the fit is inadequate" in iv["note"] for iv in r["intervals"])


def _result(**validity: object) -> SimpleNamespace:
    base = {
        "converged": True,
        "search_resolved": True,
        "at_bound": (),
        "inner_rank": 2,
        "inner_parameters": 2,
        "joint_rank": 3,
        "joint_parameters": 3,
        "regular": True,
    }
    p_value = validity.pop("p_value", 0.5)
    base.update(validity)
    return SimpleNamespace(validity=SimpleNamespace(**base), p_value=p_value)


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (_result(regular=False, converged=False), "did not converge"),
        (_result(regular=False, search_resolved=False), "search is unresolved"),
        (_result(regular=False, at_bound=("phi_deg",)), "on a bound (phi_deg)"),
        (_result(regular=False, inner_rank=1), "inner rank deficient"),
        (_result(regular=False, joint_rank=2), "joint rank deficient"),
        (_result(p_value=None), "no degrees of freedom"),
        (_result(p_value=0.999e-3), "inadequate"),
    ],
)
def test_the_interval_policy_refuses_and_says_why(result: SimpleNamespace, reason: str) -> None:
    policy = interval_policy(result)  # type: ignore[arg-type]
    assert not policy.allowed and reason in policy.reason


def test_the_interval_policy_allows_an_adequate_regular_fit() -> None:
    policy = interval_policy(_result(p_value=ADEQUATE_P_MIN))  # type: ignore[arg-type]
    assert policy.allowed and policy.adequate is True and policy.reason == ""


def test_fitting_a_project_that_is_not_ready_says_what_is_missing() -> None:
    c = client(new_session())
    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 0}))
    d = ok(c.call("project.describe"))
    assert not d["ready_to_fit"] and "torsion" in d["not_ready_reason"]
    body = error(run_fit(c), "PROJECT_NOT_READY")
    assert "torsion" in body["message"]


# --------------------------------------------------------------------------- imported geometry, end to end
def _ethane_csv(phi: float, t: np.ndarray) -> tuple[str, np.ndarray]:
    """Noiseless couplings of the ethane example at τ = phi with the order t (c1)."""
    m = parse_xyz(ETHANE_XYZ)
    geometry = TorsionGeometry.from_atoms(m.elements, m.positions, TORSION)
    hydrogens = [i for i, e in enumerate(m.elements) if e == "H"]
    pairs = list(combinations(hydrogens, 2))
    problem = imported_problem(geometry, pairs, [("1H", "1H")] * len(pairs), np.zeros(len(pairs)), np.ones(len(pairs)))
    y = problem.design(np.array([phi])) @ t
    rows = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"] + [
        f"H{a + 1},H{b + 1},{float(v)!r},0.5" for (a, b), v in zip(pairs, y, strict=True)
    ]
    return "\n".join(rows) + "\n", y


def test_imported_geometry_end_to_end() -> None:
    c = client(new_session())
    r = ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 0}))
    assert (r["n_atoms"], r["n_spins"], r["ready_to_fit"]) == (8, 6, False)
    t = ok(c.call("molecule.set_torsion", {"torsion": list(TORSION), "expected_science_revision": 1}))
    assert t["phi0"]["value"] == pytest.approx(180.0)  # the staggered example: H2 and H5 anti
    truth_phi, truth_t = 47.0, np.array([0.12, -0.03, 0.02, 0.015, -0.01])
    csv, y = _ethane_csv(truth_phi, truth_t)
    diff = ok(c.call("couplings.reconcile", {"csv": csv}))
    assert diff["complete"] and len(diff["added"]) == 15 and diff["proposed_mapping"]["H3"] == "spn_000001"
    ok(
        c.call(
            "couplings.import",
            {"csv": csv, "confirmed_mapping": diff["proposed_mapping"], "expected_science_revision": 2},
        )
    )
    d = ok(c.call("project.describe"))
    assert d["ready_to_fit"] and d["geometry"]["kind"] == "imported" and d["geometry"]["torsion"] == list(TORSION)
    assert "dihedral τ(a–i–j–b)" in d["estimand"] and d["frame"].startswith("input frame")
    preview = ok(c.call("fit.preview", {"phi": deg(truth_phi)}))
    np.testing.assert_allclose([o["value"] for o in preview["order"]], truth_t, rtol=0, atol=1e-10)
    assert preview["chi2"] < 1e-15
    fit = ok(run_fit(c))
    assert fit["chi2"] < 1e-12 and named(fit["theta"])["phi_deg"] == pytest.approx(truth_phi, abs=1e-6)
    np.testing.assert_allclose([o["value"] for o in fit["order"]], truth_t, rtol=0, atol=1e-8)
    np.testing.assert_allclose([x["calculated"]["value"] for x in fit["couplings"]], y, rtol=0, atol=1e-6)


def test_a_torsion_is_refused_on_the_template_and_checked_on_import() -> None:
    error(
        opened().call("molecule.set_torsion", {"torsion": [2, 0, 1, 5], "expected_science_revision": 1}),
        "OUT_OF_DOMAIN",
    )
    c = client(new_session())
    bad = {"xyz": ETHANE_XYZ, "name": "ethane", "torsion": [2, 0, 3, 5], "expected_science_revision": 0}
    error(c.call("project.import_xyz", bad), "INVALID_ARGUMENT", "torsion")  # 0–3 is a C–H bond, not C–C
    error(c.call("project.import_xyz", {**bad, "xyz": "2\nx\nC 0 0\n"}), "INVALID_ARGUMENT", "xyz")
    assert ok(c.call("render.describe_view"))["project_open"] is False  # nothing was replaced


# --------------------------------------------------------------------------- couplings: reconcile and import
def test_reconcile_changes_nothing_and_import_keeps_ids() -> None:
    c = opened()
    d = ok(c.call("project.describe"))
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\nH5,H6,-1124.6,0.5\n"
    diff = ok(c.call("couplings.reconcile", {"csv": csv}))
    assert diff["complete"] and [p["label"] for p in diff["added"]] == ["H5–H6"]
    assert len(diff["removed"]) == 13 and len(diff["changed"]) == 1
    # Each pair shows what the project has and what the import would set (M3 step 2).
    old_h2h3 = next(x for x in d["couplings"] if x["label"] == "H2–H3")
    changed = diff["changed"][0]
    assert changed["label"] == "H2–H3" and changed["before"] == {"value": old_h2h3["value"], "sigma": old_h2h3["sigma"]}
    assert changed["after"] == {"value": {"value": -1124.6, "unit": "Hz"}, "sigma": {"value": 0.5, "unit": "Hz"}}
    assert diff["added"][0]["before"] is None and diff["added"][0]["after"]["value"]["value"] == -1124.6
    assert all(x["after"] is None and x["before"] is not None for x in diff["removed"])
    assert ok(c.call("project.describe")) == d  # a query
    h2h3 = next(x["id"] for x in d["couplings"] if x["label"] == "H2–H3")
    r = ok(
        c.call(
            "couplings.import",
            {"csv": csv, "confirmed_mapping": diff["proposed_mapping"], "expected_science_revision": 1},
        )
    )
    assert (r["n_couplings"], r["added"], r["removed"], r["changed"]) == (2, 1, 13, 1)
    after = ok(c.call("project.describe"))
    ids = {x["label"]: x["id"] for x in after["couplings"]}
    assert ids["H2–H3"] == h2h3 and ids["H5–H6"] == "cpl_000015"  # kept, and a new number


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ({"H2": "spn_000001", "H3": "spn_000001"}, "one-to-one"),
        ({"H2": "spn_000001"}, "unresolved"),
        ({"H2": "spn_000001", "H3": "spn_000999"}, "not a spin"),
    ],
)
def test_import_refuses_a_bad_mapping(mapping: dict[str, str], message: str) -> None:
    c = opened()
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"
    body = error(
        c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1}),
        "INVALID_ARGUMENT",
        "confirmed_mapping",
    )
    assert message in body["message"]
    assert ok(c.call("render.describe_view"))["science_revision"] == 1


def test_an_import_drops_removed_ids_from_the_selection_in_the_same_transaction() -> None:
    session = new_session()
    c = client(session)
    ok(c.call("project.open_example", OPEN))
    couplings = ok(c.call("project.describe"))["couplings"]
    h2h3 = next(x["id"] for x in couplings if x["label"] == "H2–H3")
    other = next(x["id"] for x in couplings if x["label"] != "H2–H3")
    ok(c.call("view.select", {"ids": [h2h3, other, "spn_000003"]}))
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    envelope = c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1})
    ok(envelope)
    # The stored selection itself, not only its rendering (which hides unknown IDs).
    assert session.state.view.selection == (h2h3, "spn_000003")
    assert envelope["revisions"]["workspace"] == session.state.workspace_revision == 2


def test_import_refuses_an_invalid_class() -> None:
    """validate_project runs before the event: a class that is not an equivalence is refused."""
    c = opened()
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity,equivalent_pairs\nH2,H3,-1124.6,0.5,2,H2-H3 H2-H4\n"
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    body = error(
        c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1}),
        "INVALID_ARGUMENT",
        "csv",
    )
    assert "not equivalent" in body["message"]


# --------------------------------------------------------------------------- project files and replay
def test_export_and_load_round_trip_the_science(tmp_path: Any) -> None:
    session = new_session(tmp_path)
    c = client(session)
    ok(c.call("project.open_example", OPEN))
    revision = without_classes(c, 1)
    ok(c.call("model.set", model_args("rigid", "c2z", "ring-a", 0, 180, revision)))
    exported = ok(c.call("project.export"))
    assert exported["filename"].endswith(".dipolar.json")
    other = client(new_session())
    loaded = ok(other.call("project.load", {"text": exported["text"], "expected_science_revision": 0}))
    assert loaded["science_hash"] == exported["science_hash"]
    error(other.call("project.load", {"text": "{}", "expected_science_revision": 1}), "INVALID_ARGUMENT", "text")
    # Every science operation is one replayable event: the journal reproduces the science hash.
    assert replay(Journal(tmp_path / "project.events.jsonl")).science_hash == exported["science_hash"]


def test_problem_for_is_what_the_operations_fit() -> None:
    """The operations build their problem with dipolar_app.science.problem_for (one mapping)."""
    from dipolar_app.project import load_example

    problem = problem_for(load_example("biphenyl-synthetic"))
    assert problem.estimand == "rigid effective phi" and problem.order_names == ("Szz", "Delta")


# --------------------------------------------------------------------------- round 27 counterexamples
@pytest.mark.parametrize("order", ["bisector-diagonal", "c2z", "c1"])
@pytest.mark.parametrize("frame", ["bisector", "ring-a"])
def test_every_stated_equivalence_holds(order: str, frame: str) -> None:
    """Finding 1: the stated equivalences are the model's, for every order model and frame,
    checked on all 45 pairs at torsions and orders the derivation never probed."""
    from dipolar_app.science_ops import template_equivalences
    from dipolar_core.biphenyl import BiphenylGeometry, relabel_ring_b, rigid_design

    g = BiphenylGeometry()
    pairs = tuple(combinations(range(10), 2))
    found = template_equivalences(order, frame, g.r_cc, g.r_ch, g.r_inter)
    assert [label for label, _, _ in found] == ["−φ", "180° − φ", "180° + φ"]
    images = {"−φ": lambda x: -x, "180° − φ": lambda x: 180 - x, "180° + φ": lambda x: 180 + x}
    rng = np.random.default_rng(27)
    for label, relabel, rows in found:
        for phi in (37.0, 8.5, 79.0):
            t = rng.normal(0, 0.1, len(rows))
            here = rigid_design(phi, pairs, g, order=order, frame=frame) @ t  # type: ignore[arg-type]
            there_pairs = relabel_ring_b(pairs) if relabel else pairs
            there = rigid_design(images[label](phi), there_pairs, g, order=order, frame=frame) @ (np.array(rows) @ t)  # type: ignore[arg-type]
            np.testing.assert_allclose(there, here, rtol=0, atol=1e-9)


def test_c1_in_the_ring_a_frame_keeps_delta_under_the_relabelling() -> None:
    """Finding 1's counterexample: C1/ring-A at 180° − φ keeps Δ and negates Sxy and Syz."""
    c = opened()
    ok(c.call("model.set", model_args("rigid", "c1", "ring-a", 0, 180, without_classes(c, 1))))
    d = ok(c.call("project.describe"))
    assert any("(180° − φ, Szz, Delta, −Sxy, Sxz, −Syz) with ring B relabelled" in e for e in d["equivalences"])
    assert "−Δ" not in d["estimand"]


def test_the_acute_domain_states_its_label_precondition() -> None:
    d = ok(opened().call("project.describe"))
    assert "precondition" in d["estimand"]
    assert any("(180° − φ, Szz, −Delta) with ring B relabelled" in e for e in d["equivalences"])


IMPORT_CSV = "spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity,equivalent_pairs\n"


@pytest.mark.parametrize(
    ("row", "mapping", "message"),
    [
        # A label that appears only in an equivalent pair, mapped to a spin that does not exist.
        (
            "H2,H3,1,0.5,2,H2-H3 H5-H6",
            {"H2": "spn_000001", "H3": "spn_000002", "H5": "spn_000999", "H6": "spn_000005"},
            "not a spin of the project",
        ),
        ("H2,H3,1,0.5," + "9" * 5000 + ",", None, "multiplicity must be an integer"),
        ("H2,H3,1,0.5,²,", None, "multiplicity must be an integer"),
        ("H2,H3,1,0.5,1," + " ".join(["H2-H3"] * 1001), None, "more than 1000 equivalent pairs"),
    ],
)
def test_malformed_imports_are_structured_errors(row: str, mapping: dict[str, str] | None, message: str) -> None:
    """Finding 2: never an internal error, in reconcile or import."""
    c = opened()
    csv = IMPORT_CSV + row + "\n"
    args: dict[str, object] = {"csv": csv} if mapping is None else {"csv": csv, "mapping": mapping}
    assert message in error(c.call("couplings.reconcile", args), "INVALID_ARGUMENT")["message"]
    confirmed = mapping or {"H2": "spn_000001", "H3": "spn_000002"}
    body = error(
        c.call("couplings.import", {"csv": csv, "confirmed_mapping": confirmed, "expected_science_revision": 1}),
        "INVALID_ARGUMENT",
    )
    assert message in body["message"]


def test_coincident_atoms_are_refused_on_import() -> None:
    """Finding 3: a geometry the model cannot evaluate never enters the session as ready."""
    lines = ETHANE_XYZ.splitlines()
    lines[2 + 3] = lines[2 + 2]  # atom 3 onto atom 2
    xyz = "\n".join(lines) + "\n"
    c = client(new_session())
    args = {"xyz": xyz, "name": "bad", "torsion": [2, 0, 1, 5], "expected_science_revision": 0}
    assert "closer than 0.5 Å" in error(c.call("project.import_xyz", args), "INVALID_ARGUMENT")["message"]


def test_a_model_that_fails_to_evaluate_is_a_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 3: a design failure inside the domain (for example, spins meeting as the torsion
    turns) is PROJECT_NOT_READY, never INTERNAL."""
    import dipolar_core.fit

    def broken(*_: object, **__: object) -> None:
        raise ValueError("coincident spins")

    monkeypatch.setattr(dipolar_core.fit, "fit", broken)
    body = error(run_fit(opened()), "PROJECT_NOT_READY")
    assert "coincident spins" in body["message"]


def grid_xyz(n_side: int) -> str:
    atoms = [f"H {2.0 * i} {2.0 * j} 0" for i in range(n_side) for j in range(n_side)]
    return f"{len(atoms)}\nhydrogen grid\n" + "\n".join(atoms) + "\n"


def all_pairs_csv(n: int) -> str:
    rows = [f"H{a},H{b},1.0,0.5" for a, b in combinations(range(1, n + 1), 2)]
    return "spin_a,spin_b,D_obs_Hz,sigma_Hz\n" + "\n".join(rows) + "\n"


def test_an_exported_project_loads_back() -> None:
    """Finding 4: 100 hydrogens and all 4950 pairs export to about 2.5 MB, and load back."""
    c = client(new_session())
    ok(c.call("project.import_xyz", {"xyz": grid_xyz(10), "name": "grid", "expected_science_revision": 0}))
    csv = all_pairs_csv(100)
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    ok(c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1}))
    exported = ok(c.call("project.export"))
    assert len(exported["text"]) > 1 << 20
    loaded = ok(client(new_session()).call("project.load", {"text": exported["text"], "expected_science_revision": 0}))
    assert loaded["science_hash"] == exported["science_hash"]


def test_a_project_too_large_to_reload_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 4: every project in the session exports to a document project.load accepts."""
    import dipolar_app.science_ops

    c = opened()
    monkeypatch.setattr(dipolar_app.science_ops, "MAX_PROJECT_TRANSPORT", 2_000)
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"
    body = error(
        c.call(
            "couplings.import",
            {"csv": csv, "confirmed_mapping": {"H2": "spn_000001", "H3": "spn_000002"}, "expected_science_revision": 1},
        ),
        "INVALID_ARGUMENT",
    )
    assert "above the limit" in body["message"]


def test_opening_the_example_always_clears_the_selection() -> None:
    """Finding 5: an ID that exists in both projects names a different object; never keep it."""
    session = new_session()
    c = client(session)
    ok(c.call("project.import_xyz", {"xyz": grid_xyz(4), "name": "grid", "expected_science_revision": 0}))
    ok(c.call("view.select", {"ids": ["spn_000001", "spn_000011"]}))
    ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1}))
    assert session.state.view.selection == ()


# --------------------------------------------------------------------------- round 28 counterexamples
def test_the_size_limit_is_measured_as_the_document_travels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 1: characters are not bytes. An emoji is one character but 12 bytes escaped."""
    import json

    import dipolar_app.science_ops
    from dipolar_app.formats import dumps_project
    from dipolar_app.project import load_example

    project = load_example("biphenyl-synthetic").model_copy(update={"source": "😀" * 2_000})
    text = dumps_project(project)
    limit = len(text) + 1_000  # above the character count, below the escaped size
    assert len(text) < limit < len(json.dumps(text))
    monkeypatch.setattr(dipolar_app.science_ops, "MAX_PROJECT_TRANSPORT", limit)
    body = error(
        client(new_session()).call("project.load", {"text": text, "expected_science_revision": 0}), "INVALID_ARGUMENT"
    )
    assert "bytes to send" in body["message"]


@pytest.mark.parametrize(
    ("project", "message"),
    [
        (None, "must be a JSON object"),
        ({"schema_version": 1, "couplings": None}, "couplings must be a list"),
        ({"schema_version": 1, "model": "rigid"}, "model must be a JSON object"),
        ({"schema_version": 1, "couplings": [{"id": "cpl_" + "9" * 5000}]}, "cannot migrate"),
    ],
)
def test_malformed_old_documents_are_structured_errors(project: object, message: str) -> None:
    """Finding 2: a v1 document of the wrong shape is INVALID_ARGUMENT, never INTERNAL."""
    import json

    text = json.dumps({"format": "dipolar-studio-project", "schema_version": 1, "project": project})
    body = error(
        client(new_session()).call("project.load", {"text": text, "expected_science_revision": 0}),
        "INVALID_ARGUMENT",
        "text",
    )
    assert message in body["message"]
