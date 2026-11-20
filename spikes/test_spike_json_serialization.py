"""M0 spike 2: JSON serialization of units, IDs, errors and output schemas (04 §8.5).

Question: is the published contract (the registry snapshot) honest? A client that knows only the
JSON Schemas in the snapshot must be able to build valid requests and read every response. The
check uses ``jsonschema`` (an independent validator), not Pydantic, which produced the schemas.

Evidence:
  * every published schema is a valid JSON Schema (draft 2020-12);
  * every operation's examples validate against its input schema, and its results validate
    against its output schema and the success envelope;
  * every error code validates against the error envelope, which lists the codes;
  * results round-trip losslessly (JSON → model → JSON, floats exact);
  * units and IDs are visible in the schemas, so a client can see them before calling.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pytest
from dipolar_app import proposal_ops
from dipolar_app.client import LocalClient
from dipolar_app.errors import HTTP_STATUS, ErrorCode
from dipolar_app.http import _error
from dipolar_app.jobs import JobRunner
from dipolar_app.journal import Journal
from dipolar_app.operations import build_registry
from dipolar_app.policy import Principal, Tier
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.session import Session
from jsonschema import Draft202012Validator

USER = Principal(actor="user", tier=Tier.APPLY, human=True)
VIEWER = Principal(actor="script:viewer", tier=Tier.READ, human=False)
AGENT = Principal(actor="agent:test", tier=Tier.PROPOSE, human=False)

REGISTRY = build_registry()
SNAPSHOT: dict[str, Any] = json.loads(json.dumps(REGISTRY.snapshot()))  # exactly what GET /api/v1/registry returns
OPS = {op["name"]: op for op in SNAPSHOT["operations"]}


def validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_valid(schema: dict[str, Any], instance: Any) -> None:
    errors = sorted(validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors]


def opened_client(principal: Principal = USER, journal: Journal | None = None) -> LocalClient:
    session = Session(journal, contract_version=CONTRACT_VERSION)
    JobRunner(session, mode="thread")
    LocalClient(REGISTRY, session, USER).call(
        "project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}
    )
    return LocalClient(REGISTRY, session, principal)


#: Operations whose example needs an imported project rather than the opened template example.
NEEDS_IMPORTED = {"molecule.set_torsion"}
#: Operations whose examples need imported benzene (V1.3: the fixed-geometry declarations).
NEEDS_BENZENE = {"molecule.set_symmetry", "molecule.set_isotope"}
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
#: Benzene in its D6h frame (z normal, x through carbon 0): six carbons, then six hydrogens.
BENZENE_XYZ = "12\nbenzene\n" + "".join(
    f"{e} {float(r * math.cos(math.radians(60 * k)))!r} {float(r * math.sin(math.radians(60 * k)))!r} 0.0\n"
    for e, r in (("C", 1.3914), ("H", 2.4716))
    for k in range(6)
)


def benzene_client(group: str | None = None, axes: list[list[float]] | None = None) -> LocalClient:
    """Imported benzene at science revision 1, or 2 with a declared symmetry."""
    session = Session(None, contract_version=CONTRACT_VERSION)
    JobRunner(session, mode="thread")
    c = LocalClient(REGISTRY, session, USER)
    args = {"xyz": BENZENE_XYZ, "name": "benzene", "expected_science_revision": 0}
    assert c.call("project.import_xyz", args)["ok"]
    if group is not None:
        symmetry = {"point_group": group, "axes": axes or IDENTITY}
        assert c.call("molecule.set_symmetry", {"symmetry": symmetry, "expected_science_revision": 1})["ok"]
    return c


def client_for(name: str, example: dict[str, Any] | None = None) -> LocalClient:
    """A client whose session has a project the example can use."""
    if name == "model.set" and example is not None and example.get("kind") == "fixed":
        return benzene_client("D6h")
    if name == "molecule.set_isotope":  # carbon 0 lies on the C2 axis of this C2v frame
        return benzene_client("C2v", [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
    if name in NEEDS_BENZENE:
        return benzene_client()
    if name not in NEEDS_IMPORTED:
        return opened_client()
    session = Session(None, contract_version=CONTRACT_VERSION)
    op = REGISTRY.get("project.import_xyz")
    assert op is not None
    assert LocalClient(REGISTRY, session, USER).call("project.import_xyz", dict(op.examples[0]))["ok"]
    return LocalClient(REGISTRY, session, USER)


JUMP = {
    "kind": "jump4",
    "order": "bisector-diagonal",
    "frame": "bisector",
    "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
}


def prepared(name: str, example: dict[str, Any] | None = None) -> tuple[LocalClient, dict[str, Any]]:
    """A client in a state the operation's examples can use, and its first example with the
    current science revision filled in (M2 step 2: undo needs a change, accept needs a proposal)."""
    c = client_for(name, example)
    if name in ("history.undo", "history.redo"):
        assert c.call("model.set", {**JUMP, "expected_science_revision": 1})["ok"]
        if name == "history.redo":
            assert c.call("history.undo", {"expected_science_revision": 2})["ok"]
    if name in ("proposal.get", "proposal.accept", "proposal.reject"):
        assert c.call("proposal.create", dict(OPS["proposal.create"]["examples"][0]))["ok"]
    if name.startswith(("job.", "run.")):  # a finished fit: job_000001 and run_000001
        assert c.call("fit.run", {"expected_science_revision": 1})["ok"]
        assert c.call("job.wait", {"job_id": "job_000001", "timeout_s": 30})["result"]["finished"]
    return c, c.call("render.describe_view")["revisions"]


def example_args(name: str, example: dict[str, Any], revisions: dict[str, Any]) -> dict[str, Any]:
    args = dict(example)
    if "expected_science_revision" in args:
        args["expected_science_revision"] = revisions["science"]
    return args


def test_every_published_schema_is_valid_json_schema() -> None:
    envelopes = SNAPSHOT["envelopes"]
    schemas = [envelopes["request"], envelopes["success"], envelopes["error"]]
    for op in SNAPSHOT["operations"]:
        schemas += [op["input_schema"], op["output_schema"]]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    assert len(schemas) == 3 + 2 * len(OPS)


@pytest.mark.parametrize("name", sorted(OPS))
def test_examples_and_results_match_the_published_schemas(name: str) -> None:
    op = OPS[name]
    assert op["examples"], f"{name} publishes no example"
    for example in op["examples"]:
        assert_valid(op["input_schema"], example)
        assert_valid(SNAPSHOT["envelopes"]["request"], {"args": example})
        c, revisions = prepared(name, example)
        envelope = c.call(name, example_args(name, example, revisions))
        assert envelope["ok"], envelope
        assert_valid(SNAPSHOT["envelopes"]["success"], envelope)
        assert_valid(op["output_schema"], envelope["result"])
        if op["kind"] == "command":  # the dry-run report validates too
            c, revisions = prepared(name, example)
            dry = c.call(name, example_args(name, example, revisions), dry_run=True)
            assert dry["ok"] and dry["dry_run"] is not None, dry
            assert_valid(SNAPSHOT["envelopes"]["success"], dry)


@pytest.mark.parametrize("name", sorted(OPS))
def test_results_round_trip_losslessly(name: str) -> None:
    """JSON → output model (strict) → JSON gives the same document; every float is exact."""
    op = REGISTRY.get(name)
    assert op is not None
    c, revisions = prepared(name)
    result = c.call(name, example_args(name, OPS[name]["examples"][0], revisions))["result"]
    text = json.dumps(result, allow_nan=False)
    again = op.output_model.model_validate_json(text, strict=True).model_dump(mode="json")
    assert again == result
    assert json.dumps(again, allow_nan=False) == text


def test_units_and_ids_are_visible_in_the_schemas() -> None:
    """A client sees the unit of every quantity and the pattern of every ID before calling."""
    preview_in = OPS["fit.preview"]["input_schema"]
    degrees = preview_in["$defs"]["Degrees"]
    assert degrees["properties"]["unit"] == {"const": "deg", "title": "Unit", "type": "string"}
    assert degrees["required"] == ["value", "unit"] and degrees["additionalProperties"] is False
    select_in = OPS["view.select"]["input_schema"]
    assert select_in["properties"]["ids"]["items"]["pattern"] == r"^(spn|cpl)_[0-9]{6}$"
    revision = OPS["project.open_example"]["input_schema"]["properties"]["expected_science_revision"]
    assert revision["minimum"] == 0 and revision["maximum"] == 2**53 - 1
    preview_out = json.dumps(OPS["fit.preview"]["output_schema"])
    for unit in ('"const": "Hz"', '"const": "deg"'):
        assert unit in preview_out


def produce_every_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[ErrorCode, dict[str, Any]]:
    seen: dict[ErrorCode, dict[str, Any]] = {}

    def keep(envelope: dict[str, Any]) -> None:
        assert not envelope["ok"], envelope
        seen[ErrorCode(envelope["error"]["code"])] = envelope

    fresh = LocalClient(REGISTRY, Session(None, contract_version=CONTRACT_VERSION), USER)
    keep(fresh.call("fit.preview", {"phi": {"value": 37.0, "unit": "deg"}}))  # NO_PROJECT
    user = opened_client()
    keep(user.call("fit.preview", {"phi": {"value": "37", "unit": "deg"}}))  # INVALID_ARGUMENT
    keep(user.call("no.such_operation"))  # UNKNOWN_OPERATION
    keep(user.call("fit.preview", {"phi": {"value": 120.0, "unit": "deg"}}))  # OUT_OF_DOMAIN
    keep(user.call("view.select", {"ids": ["cpl_999999"]}))  # ID_NOT_FOUND
    keep(client_for("molecule.set_torsion").call("fit.preview", {"phi": {"value": 60.0, "unit": "deg"}}))
    # PROJECT_NOT_READY: the imported example has no couplings yet
    keep(user.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}))
    keep(opened_client(VIEWER).call("view.select", {"ids": []}))  # CAPABILITY_DENIED
    keep(
        opened_client(AGENT).call(
            "project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1}
        )
    )  # PROPOSAL_REQUIRED

    # M2 step 2: request IDs, undo and proposals.
    assert user.call("view.select", {"ids": []}, request_id="k")["ok"]
    keep(user.call("view.select", {"ids": ["cpl_000001"]}, request_id="k"))  # IDEMPOTENCY_KEY_REUSED
    keep(user.call("history.undo", {"expected_science_revision": 1}))  # NOTHING_TO_UNDO
    agent = LocalClient(REGISTRY, user._session, AGENT)
    proposal = {"steps": [{"operation": "model.set", "args": {**JUMP, "expected_science_revision": 1}}]}
    for _ in range(proposal_ops.MAX_PENDING):
        assert agent.call("proposal.create", proposal)["ok"]
    keep(agent.call("proposal.create", proposal))  # QUOTA_EXCEEDED
    assert user.call("model.set", {**JUMP, "expected_science_revision": 1})["ok"]
    keep(user.call("proposal.accept", {"proposal_id": "prp_000001"}))  # PROPOSAL_STALE
    assert user.call("proposal.reject", {"proposal_id": "prp_000001"})["ok"]
    keep(user.call("proposal.reject", {"proposal_id": "prp_000001"}))  # PROPOSAL_CLOSED

    journal = Journal(tmp_path / "events.jsonl")
    failing = opened_client(journal=journal)

    def broken_fsync(fd: int) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(os, "fsync", broken_fsync)
    keep(failing.call("view.select", {"ids": ["cpl_000001"]}))  # JOURNAL_FAILED
    monkeypatch.undo()

    # V1.3: the fixed-geometry codes.
    benzene = benzene_client("D6h")
    revision = 2
    keep(benzene.call("molecule.set_isotope", {"atom": 0, "mass_number": 13, "expected_science_revision": revision}))
    # SYMMETRY_NOT_SATISFIED: carbon-13 breaks D6h
    keep(benzene.call("molecule.set_isotope", {"atom": 0, "mass_number": 14, "expected_science_revision": revision}))
    # ISOTOPE_NOT_SUPPORTED
    for symmetry in ({"point_group": "C3v", "axes": IDENTITY}, {"point_group": "D6h", "medium": "chiral"}):
        keep(benzene.call("molecule.set_symmetry", {"symmetry": symmetry, "expected_science_revision": revision}))
    # POINT_GROUP_NOT_SUPPORTED, MEDIUM_NOT_SUPPORTED
    csv = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH7,H8,-100.0,1.0\nH8,H9,-100.0,1.0\n"
    mapping = {f"H{k}": f"spn_{k - 6:06d}" for k in (7, 8, 9)}
    assert benzene.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 2})[
        "ok"
    ]
    fixed = {"kind": "fixed", "order": "point-group", "frame": "symmetry", "expected_science_revision": 3}
    keep(benzene.call("model.set", fixed))  # OBSERVATIONS_CONFLICT: two rows in the ortho orbit
    assert benzene.call("couplings.remove", {"coupling_ids": ["cpl_000002"], "expected_science_revision": 3})["ok"]
    assert benzene.call("model.set", {**fixed, "expected_science_revision": 4})["ok"]
    keep(benzene.call("fit.preview", {"phi": {"value": 0.0, "unit": "deg"}}))  # NO_TORSION
    import dipolar_core.symmetry

    monkeypatch.setattr(dipolar_core.symmetry, "MAX_FIT_ROWS", 0)
    keep(benzene.call("fit.run", {"expected_science_revision": 5}))  # FIT_TOO_LARGE (the limit lowered)
    monkeypatch.undo()

    for code in (ErrorCode.UNAUTHENTICATED, ErrorCode.PAYLOAD_TOO_LARGE, ErrorCode.INTERNAL):  # HTTP adapter only
        response = _error(code, "from the HTTP adapter", operation="fit.preview")
        assert response.status_code == HTTP_STATUS[code]
        keep(json.loads(bytes(response.body)))
    return seen


def test_every_error_code_matches_the_error_envelope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = produce_every_error(monkeypatch, tmp_path)
    assert set(seen) == set(ErrorCode), sorted(set(ErrorCode) - set(seen))
    schema = SNAPSHOT["envelopes"]["error"]
    published = schema["$defs"]["ErrorCode"]["enum"]
    assert sorted(published) == sorted(code.value for code in ErrorCode)
    for envelope in seen.values():
        assert_valid(schema, envelope)
    assert seen[ErrorCode.REVISION_CONFLICT]["error"]["details"] == {"current_science_revision": 1}
    assert seen[ErrorCode.INVALID_ARGUMENT]["error"]["offending_field"] == "phi.value"
