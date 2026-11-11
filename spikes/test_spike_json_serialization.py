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
import os
from pathlib import Path
from typing import Any

import pytest
from dipolar_app.client import LocalClient
from dipolar_app.errors import HTTP_STATUS, ErrorCode
from dipolar_app.http import _error
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
    LocalClient(REGISTRY, session, USER).call(
        "project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}
    )
    return LocalClient(REGISTRY, session, principal)


#: Operations whose example needs an imported project rather than the opened template example.
NEEDS_IMPORTED = {"molecule.set_torsion"}


def client_for(name: str) -> LocalClient:
    """A client whose session is at science revision 1 with a project the example can use."""
    if name not in NEEDS_IMPORTED:
        return opened_client()
    session = Session(None, contract_version=CONTRACT_VERSION)
    op = REGISTRY.get("project.import_xyz")
    assert op is not None
    assert LocalClient(REGISTRY, session, USER).call("project.import_xyz", dict(op.examples[0]))["ok"]
    return LocalClient(REGISTRY, session, USER)


def test_every_published_schema_is_valid_json_schema() -> None:
    schemas = [SNAPSHOT["envelopes"]["success"], SNAPSHOT["envelopes"]["error"]]
    for op in SNAPSHOT["operations"]:
        schemas += [op["input_schema"], op["output_schema"]]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    assert len(schemas) == 2 + 2 * len(OPS)


@pytest.mark.parametrize("name", sorted(OPS))
def test_examples_and_results_match_the_published_schemas(name: str) -> None:
    op = OPS[name]
    assert op["examples"], f"{name} publishes no example"
    for example in op["examples"]:
        assert_valid(op["input_schema"], example)
        c = client_for(name)
        args = dict(example)
        if "expected_science_revision" in args:
            args["expected_science_revision"] = 1  # the example opened the project once already
        envelope = c.call(name, args)
        assert envelope["ok"], envelope
        assert_valid(SNAPSHOT["envelopes"]["success"], envelope)
        assert_valid(op["output_schema"], envelope["result"])


@pytest.mark.parametrize("name", sorted(OPS))
def test_results_round_trip_losslessly(name: str) -> None:
    """JSON → output model (strict) → JSON gives the same document; every float is exact."""
    op = REGISTRY.get(name)
    assert op is not None
    args = dict(OPS[name]["examples"][0])
    if "expected_science_revision" in args:
        args["expected_science_revision"] = 1
    c = client_for(name)
    result = c.call(name, args)["result"]
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

    journal = Journal(tmp_path / "events.jsonl")
    failing = opened_client(journal=journal)

    def broken_fsync(fd: int) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(os, "fsync", broken_fsync)
    keep(failing.call("view.select", {"ids": ["cpl_000001"]}))  # JOURNAL_FAILED
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
