"""The slice through the Python adapter: registry → policy → session → journal (04 §7, §8.1, §8.3)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import AGENT, ROOT, VIEWER, client, expected, new_session
from dipolar_app.project import load_example

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}


def phi_args(value: object, unit: str = "deg") -> dict[str, object]:
    return {"phi": {"value": value, "unit": unit}}


def test_bundled_example_equals_dataset_csv() -> None:
    project = load_example("biphenyl-synthetic")
    labels = {s.id: s.label for s in project.molecule.spins}
    rows = list(csv.DictReader((ROOT / "datasets" / "biphenyl-synthetic" / "couplings.csv").open()))
    assert len(rows) == len(project.couplings) == 14
    for row, c in zip(rows, project.couplings, strict=True):
        assert (labels[c.spin_a], labels[c.spin_b]) == (row["spin_a"], row["spin_b"])
        assert c.value.value == float(row["D_obs_Hz"])
        assert c.sigma.value == float(row["sigma_Hz"])
        assert c.multiplicity == int(row["multiplicity"])
        assert " ".join(c.equivalent_pairs) == row["equivalent_pairs"]


def test_preview_reproduces_frozen_fixture() -> None:
    c = client(new_session())
    assert c.call("project.open_example", OPEN)["ok"]
    e = expected("noisy_fixture.json")["expected"]
    tol = expected("spec.json")["tolerances"]["regression"]
    env = c.call("fit.preview", phi_args(e["phi_deg"]))
    assert env["ok"], env
    r = env["result"]
    assert r["order"]["Szz"] == pytest.approx(e["Szz"], abs=tol["S_atol"])
    assert r["order"]["Delta"] == pytest.approx(e["Delta"], abs=tol["S_atol"])
    assert r["chi2"] == pytest.approx(e["objective"], rel=tol["objective_rtol"])
    calculated = [row["calculated"]["value"] for row in r["couplings"]]
    assert calculated == pytest.approx(e["predictions_Hz"], abs=tol["predictions_atol_Hz"])
    assert all(row["calculated"]["unit"] == "Hz" for row in r["couplings"])
    assert r["n_obs"] == e["N"] == 14
    assert r["validity"] == {
        "inner_rank": 2,
        "inner_parameters": 2,
        "inner_condition_number": pytest.approx(e["validity"]["inner_condition_number"], rel=1e-9),
        "physically_admissible": True,
    }
    assert r["phi"] == {"value": e["phi_deg"], "unit": "deg"}
    assert r["science_revision"] == 1
    assert "not a fit" in r["statement"]


def test_revisions_are_separate_and_queries_change_nothing() -> None:
    s = new_session()
    c = client(s)
    c.call("project.open_example", OPEN)
    science = (s.state.science_revision, s.state.science_hash)
    seq = s.state.seq

    preview = c.call("fit.preview", phi_args(37.0))
    c.call("project.describe")
    c.call("render.describe_view")
    assert (s.state.seq, s.state.science_revision, s.state.workspace_revision) == (seq, 1, 0)

    ids = [row["id"] for row in preview["result"]["couplings"]]
    sel = c.call("view.select", {"ids": [ids[3], ids[0], ids[3]]})
    assert sel["ok"], sel
    assert [x["id"] for x in sel["result"]["selection"]] == [ids[3], ids[0]]  # de-duplicated, ordered
    assert sel["revisions"] == {"science": 1, "workspace": 1}
    assert (s.state.science_revision, s.state.science_hash) == science  # view never touches science

    again = c.call("view.select", {"ids": [ids[3], ids[0]]})
    assert again["revisions"]["workspace"] == 1  # unchanged selection: no event, no revision
    assert s.state.seq == seq + 1


def test_reopening_clears_the_selection_in_the_same_transaction() -> None:
    s = new_session()
    c = client(s)
    c.call("project.open_example", OPEN)
    c.call("view.select", {"ids": ["cpl_000001"]})
    env = c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1})
    assert env["ok"]
    assert env["revisions"] == {"science": 2, "workspace": 2}
    assert s.state.view.selection == ()
    assert s.state.seq == 3


def test_revision_conflict_mutates_nothing() -> None:
    s = new_session()
    c = client(s)
    c.call("project.open_example", OPEN)
    before = s.state
    env = c.call("project.open_example", OPEN)  # stale: the science revision is now 1
    assert not env["ok"]
    assert env["error"]["code"] == "REVISION_CONFLICT"
    assert env["error"]["offending_field"] == "expected_science_revision"
    assert env["error"]["details"] == {"current_science_revision": 1}
    assert s.state is before


def test_missing_revision_check_is_a_validation_error() -> None:
    env = client(new_session()).call("project.open_example", {"name": "biphenyl-synthetic"})
    assert env["error"]["code"] == "INVALID_ARGUMENT"
    assert env["error"]["offending_field"] == "expected_science_revision"


@pytest.mark.parametrize(
    ("args", "field"),
    [
        (phi_args(37.0, "rad"), "phi.unit"),
        ({"phi": 37.0}, "phi"),
        ({"phi": {"value": "NaN", "unit": "deg"}}, "phi.value"),
        ({**phi_args(37.0), "actor": "user"}, "actor"),
        ({"phi": {"value": 37.0, "unit": "deg", "extra": 1}}, "phi.extra"),
    ],
)
def test_structured_validation_errors(args: dict[str, object], field: str) -> None:
    c = client(new_session())
    c.call("project.open_example", OPEN)
    env = c.call("fit.preview", args)
    assert env["ok"] is False
    assert env["error"]["code"] == "INVALID_ARGUMENT"
    assert env["error"]["offending_field"] == field
    assert env["error"]["hint"]


@pytest.mark.parametrize(
    ("operation", "args", "field"),
    [
        ("fit.preview", phi_args("37"), "phi.value"),
        ("fit.preview", phi_args(True), "phi.value"),
        ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": "1"}, None),
        ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1.0}, None),
        ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": True}, None),
        ("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 2**53}, None),
        ("view.select", {"ids": "cpl_000001"}, "ids"),
    ],
)
def test_no_type_coercion(operation: str, args: dict[str, object], field: str | None) -> None:
    """Spike 2: validation is strict. A string is not a number and true is not 1, so a wrong type
    can never pass a revision check by accident."""
    c = client(new_session())
    c.call("project.open_example", OPEN)
    env = c.call(operation, args)
    assert env["ok"] is False and env["error"]["code"] == "INVALID_ARGUMENT", env
    assert env["error"]["offending_field"] == (field or "expected_science_revision")
    assert c.call("render.describe_view")["result"]["science_revision"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_python_adapter_rejects_non_finite_numbers(value: float) -> None:
    """The Python adapter returns a structured error for NaN and ±inf instead of raising."""
    c = client(new_session())
    c.call("project.open_example", OPEN)
    env = c.call("fit.preview", phi_args(value))
    assert env["ok"] is False and env["error"]["code"] == "INVALID_ARGUMENT"
    assert "finite" in env["error"]["message"]


def test_domain_project_and_id_errors() -> None:
    c = client(new_session())
    assert c.call("fit.preview", phi_args(37.0))["error"]["code"] == "NO_PROJECT"
    assert c.call("nope.op")["error"]["code"] == "UNKNOWN_OPERATION"
    c.call("project.open_example", OPEN)
    out = c.call("fit.preview", phi_args(120.0))
    assert (out["error"]["code"], out["error"]["offending_field"]) == ("OUT_OF_DOMAIN", "phi.value")
    sel = c.call("view.select", {"ids": ["cpl_000001", "cpl_000099"]})
    assert (sel["error"]["code"], sel["error"]["offending_field"]) == ("ID_NOT_FOUND", "ids[1]")
    bad = c.call("view.select", {"ids": ["H2"]})  # labels are not IDs (D5)
    assert bad["error"]["code"] == "INVALID_ARGUMENT"


def test_policy_matrix_from_credentials() -> None:
    s = new_session()
    client(s).call("project.open_example", OPEN)
    viewer, agent = client(s, VIEWER), client(s, AGENT)

    assert viewer.call("fit.preview", phi_args(37.0))["ok"]  # bounded preview: allowed for read
    assert viewer.call("render.describe_view")["ok"]
    assert viewer.call("view.select", {"ids": ["cpl_000001"]})["error"]["code"] == "CAPABILITY_DENIED"
    denied = viewer.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1})
    assert denied["error"]["code"] == "CAPABILITY_DENIED"

    assert agent.call("view.select", {"ids": ["cpl_000001"]})["ok"]  # view writes: direct and logged
    proposal = agent.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1})
    assert proposal["error"]["code"] == "PROPOSAL_REQUIRED"
    assert s.state.science_revision == 1


def test_registry_examples_validate() -> None:
    from dipolar_app.operations import build_registry

    registry = build_registry()
    for name in registry.names:
        op = registry.get(name)
        assert op is not None and op.examples, name
        for example in op.examples:
            op.input_model.model_validate(example)


def test_registry_snapshot_is_committed() -> None:
    """D13/D20: any contract change shows up here and needs a CONTRACT_VERSION decision."""
    import json
    import os

    from dipolar_app.operations import build_registry

    path = Path(__file__).resolve().parents[1] / "registry.snapshot.json"
    current = json.dumps(build_registry().snapshot(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("DIPOLAR_UPDATE_SNAPSHOT") == "1":
        path.write_text(current, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == current, (
        "registry contract changed: review, bump CONTRACT_VERSION if needed (D20), then rerun with "
        "DIPOLAR_UPDATE_SNAPSHOT=1"
    )
